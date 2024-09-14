from functools import partial
import json
import os
from pathlib import Path
import sys
from typing import Any, Callable, Dict, Optional, TextIO, Union

from google.protobuf.json_format import MessageToDict
from snowplow_tracker import Subject
from snowplow_tracker.typing import FailureCallback

from dbt_common.helper_types import WarnErrorOptions
from dbt_common.invocation import get_invocation_id
from dbt_common.events.base_types import BaseEvent, EventLevel, EventMsg
from dbt_common.events.cookie import Cookie
from dbt_common.events.event_manager_client import get_event_manager
from dbt_common.events.logger import LoggerConfig, LineFormat
from dbt_common.events.tracker import TrackerConfig
from dbt_common.events.types import DisableTracking, Note
from dbt_common.events.user import User
from dbt_common.exceptions import EventCompilationError, scrub_secrets, env_secrets
from dbt_common.utils.encoding import ForgivingJSONEncoder


LOG_VERSION = 3
metadata_vars: Optional[Dict[str, str]] = None
_METADATA_ENV_PREFIX = "DBT_ENV_CUSTOM_ENV_"
WARN_ERROR_OPTIONS = WarnErrorOptions(include=[], exclude=[])
WARN_ERROR = False


# This global, and the following two functions for capturing stdout logs are
# an unpleasant hack we intend to remove as part of API-ification. The GitHub
# issue #6350 was opened for that work.
CAPTURE_STREAM: Optional[TextIO] = None


def stdout_filter(
    log_cache_events: bool,
    line_format: LineFormat,
    msg: EventMsg,
) -> bool:
    return msg.info.name not in ["CacheAction", "CacheDumpGraph"] or log_cache_events


def get_stdout_config(
    line_format: LineFormat,
    use_colors: bool,
    level: EventLevel,
    log_cache_events: bool,
) -> LoggerConfig:
    return LoggerConfig(
        name="stdout_log",
        level=level,
        use_colors=use_colors,
        line_format=line_format,
        scrubber=env_scrubber,
        filter=partial(
            stdout_filter,
            log_cache_events,
            line_format,
        ),
        invocation_id=get_invocation_id(),
        output_stream=sys.stdout,
    )


def get_logfile_config(
    name: str,
    log_path: str,
    line_format: Optional[LineFormat] = LineFormat.PlainText,
    use_colors: Optional[bool] = False,
    log_file_max_bytes: Optional[int] = 10 * 1024 * 1024,
) -> LoggerConfig:
    return LoggerConfig(
        name=name,
        line_format=line_format,
        level=EventLevel.DEBUG,  # File log is *always* debug level
        use_colors=use_colors,
        invocation_id=get_invocation_id(),
        output_file_name=log_path,
        output_file_max_bytes=log_file_max_bytes,
    )


def make_log_dir_if_missing(log_path: Union[Path, str]) -> None:
    if isinstance(log_path, str):
        log_path = Path(log_path)
    log_path.mkdir(parents=True, exist_ok=True)


def env_scrubber(msg: str) -> str:
    return scrub_secrets(msg, env_secrets())


# used for integration tests
def capture_stdout_logs(stream: TextIO) -> None:
    global CAPTURE_STREAM
    CAPTURE_STREAM = stream


def stop_capture_stdout_logs() -> None:
    global CAPTURE_STREAM
    CAPTURE_STREAM = None


def get_capture_stream() -> Optional[TextIO]:
    return CAPTURE_STREAM


# returns a dictionary representation of the event fields.
# the message may contain secrets which must be scrubbed at the usage site.
def msg_to_json(msg: EventMsg) -> str:
    msg_dict = msg_to_dict(msg)
    raw_log_line = json.dumps(msg_dict, sort_keys=True, cls=ForgivingJSONEncoder)
    return raw_log_line


def msg_to_dict(msg: EventMsg) -> dict:
    msg_dict = dict()
    try:
        msg_dict = MessageToDict(
            msg,
            preserving_proto_field_name=True,
            including_default_value_fields=True,  # type: ignore
        )
    except Exception as exc:
        event_type = type(msg).__name__
        fire_event(
            Note(msg=f"type {event_type} is not serializable. {str(exc)}"), level=EventLevel.WARN
        )
    # We don't want an empty NodeInfo in output
    if (
        "data" in msg_dict
        and "node_info" in msg_dict["data"]
        and msg_dict["data"]["node_info"]["node_name"] == ""
    ):
        del msg_dict["data"]["node_info"]
    return msg_dict


def warn_or_error(event, node=None) -> None:
    event_name = type(event).__name__
    if WARN_ERROR or WARN_ERROR_OPTIONS.includes(event_name):
        raise EventCompilationError(event.message(), node)
    elif not WARN_ERROR_OPTIONS.silenced(event_name):
        fire_event(event)


# an alternative to fire_event which only creates and logs the event value
# if the condition is met. Does nothing otherwise.
def fire_event_if(
    conditional: bool, lazy_e: Callable[[], BaseEvent], level: Optional[EventLevel] = None
) -> None:
    if conditional:
        fire_event(lazy_e(), level=level)


# top-level method for accessing the new eventing system
# this is where all the side effects happen branched by event type
# (i.e. - mutating the event history, printing to stdout, logging
# to files, etc.)
def fire_event(e: BaseEvent, level: Optional[EventLevel] = None) -> None:
    get_event_manager().fire_event(e, level=level)


def get_metadata_vars() -> Dict[str, str]:
    global metadata_vars
    if metadata_vars is None:
        metadata_vars = {
            k[len(_METADATA_ENV_PREFIX) :]: v
            for k, v in os.environ.items()
            if k.startswith(_METADATA_ENV_PREFIX)
        }
    return metadata_vars


def reset_metadata_vars() -> None:
    global metadata_vars
    metadata_vars = None


def _default_on_failure(num_ok, unsent):
    """
    num_ok will always be 0, unsent will always be 1 entry long
    because the buffer is length 1, so not much to talk about

    TODO: add `disable_tracking` as a callback on `DisableTracking`
    """
    fire_event(DisableTracking())


def snowplow_config(
    user: User,
    endpoint: str,
    protocol: Optional[str] = "https",
    on_failure: Optional[FailureCallback] = _default_on_failure,
) -> TrackerConfig:
    return TrackerConfig(
        invocation_id=user.invocation_id,
        endpoint=endpoint,
        protocol=protocol,
        on_failure=on_failure,
    )


def enable_tracking(tracker, user: User):
    cookie = _get_cookie(user)
    user.enable_tracking(cookie)

    subject = Subject()
    subject.set_user_id(cookie.get("id"))
    tracker.set_subject(subject)


def disable_tracking(tracker, user: User):
    user.disable_tracking()
    tracker.set_subject(None)


def _get_cookie(user: User) -> Dict[str, Any]:
    if cookie := user.cookie:
        return cookie
    return _set_cookie(user)


def _set_cookie(user: User) -> Dict[str, Any]:
    """
    If the user points dbt to a profile directory which exists AND
    contains a profiles.yml file, then we can set a cookie. If the
    specified folder does not exist, or if there is not a profiles.yml
    file in this folder, then an inconsistent cookie can be used. This
    will change in every dbt invocation until the user points to a
    profile dir file which contains a valid profiles.yml file.

    See: https://github.com/dbt-labs/dbt-core/issues/1645
    """
    if user.profile.exists():
        cookie = Cookie(user.directory)
        user.cookie = cookie.as_dict()
        return user.cookie
    return {}
