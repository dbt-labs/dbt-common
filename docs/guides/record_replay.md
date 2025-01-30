# The Record/Replay Subsystem
The `dbt_common.record` module provides a semi-experimental mechanism for recording dbt's interaction with external systems during a command invocation. The recording can be used as a record of how dbt behaved during an invocation, or it "replayed" later by a different version of dbt to compare its behavior to the original, without actually interacting with a data warehouse, the filesystem, or any other external process.

For now, this mechanism should be regarded as an unstable preview. Details of how it works, which functions are annotated, and how annotations are made, are subject to arbitrary changes.

If dbt's internal behavior is sufficiently deterministic, we will be able to use the record/replay mechanism in several interesting test and debugging scenarios, but our plan is to start by developing a robust record capability, since it would immediately support the testing scenarios we are most interested in. 

This mechanism is a work in progress. Not all of dbt's interactions are recorded as of this writing. The rest of this document explains how the mechanism works and how to improve its coverage, so that more people can help with the effort.
  

## How it Works
  
We assume that every interaction between dbt and an external system is performed via a function call, and that all of those function calls are marked with the `@record_function` decorator. When recording, the parameters passed to and results returned from these annotated functions are recorded, so that they can be persisted to file for later comparison or for use with replay.
  
Now, suppose you recorded the data warehouse interactions while running v1 of `dbt-core` and you want to make sure that refactorizations you have done for v2 did not change the way dbt interacts with the warehouse. You can simply record a run with the same command using v2 and compare the two recordings to see if any of the SQL sent to the warehouse has changed. This may mean ignoring certain changes to whitespace or formatting which is also handled by the record/replay mechanism.
  
One problem which might arise in the scenario just described is that the results of introspective queries returned from the warehouse differ between runs, subtly changing dbt's behavior. This is where the replay mechanism will help us. When replay is enabled, an existing recording is used to mock out the function calls annotated with @record_function. The parameters to the function will be used to locate the corresponding call in the recording, and the recorded return value for that call is returned. In principle, all interaction with external systems can be mocked out this way, allowing dbt to be isolated and any deviation from its behavior in the recording can be noted.
  
## How to Use It
  
An example of how the mechanism is applied can be found in ./clients/system.py with the load_file_contents() function. Notice the decorator applied to this function:
```python
@record_function(LoadFileRecord)
```
When record and replay are disabled, this decorator is a no-op, but when one of them is enabled it implements the behaviors described above.  
  
Note also the `LoadFileRecord` class passed as a parameter to this decorator. This is (and must be) a class with the two properties `params_cls`, and `result_cls` specified. The class itself is registered with the record/replay mechanism by annotating it with `@Recorder.register_record_type`.  
  
The final detail needed is to define the classes specified by `params_cls` and `result_cls`, which must be dataclasses with properties whose order and names correspond to the parameters passed to the recorded function. In this case those are the `LoadFileParams` and `LoadFileResult` classes, respectively.

With these decorators applied and classes defined, dbt is able to record all file access during a run, and mock out the accesses during replay, isolating dbt from actually loading files. At least it would if dbt only used this function for all file access, which is only mostly true. We hope to continue improving the usefulness of this mechanism by adding more recorded functions and routing more operations through them.

## How to record/replay

Record/replay behavior is activated and configured via environment variables. When DBT_RECORDER_MODE is unset, the entire subsystem is disabled, and the decorators described above have no effect at all. This helps isolate the subsystem from core's application code, reducing the risk of performance impact or regressions.

The record/replay subsystem is activated by setting the `DBT_RECORDER_MODE` variable to `replay`, `record`, or `diff`, case insensitive.  Invalid values are ignored and do not throw exceptions.

`DBT_RECORDER_TYPES` is optional.  It indicates which types to filter the results by and expects a list of strings values for the `Record` subclasses or groups of such classes. For example, all records of database/DWH interaction performed by adapters belong to the `Database` group. Any invalid type or group name will be ignored.  `all` is a valid value for this variable and has the same effect as not populating the variable.


```bash
DBT_RECORDER_MODE=record DBT_RECORDER_TYPES=Database dbt run
```

replay need the file to replay
```bash
DBT_RECORDER_MODE=replay DBT_RECORDER_FILE_PATH=recording.json dbt run
```

## Final Thoughts
  
We are aware of the potential limitations of this mechanism, since it makes several strong assumptions, not least of which are:
  
1. Every important interaction with an external system can be modeled as a function call.  
2. Every important interaction can be recorded without creating an impractically large output file.  
3. The recorded functions do not have important side effects within dbt itself which would not be duplicated during replay.

Nonetheless, we are excited to see how far the experiment takes us and how we can apply it to automatically detect changes in dbt's behavior during testing and upgrades.
