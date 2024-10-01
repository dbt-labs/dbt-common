# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: common_types.proto
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder

# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from google.protobuf import timestamp_pb2 as google_dot_protobuf_dot_timestamp__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(
    b'\n\x12\x63ommon_types.proto\x12\x0bproto_types\x1a\x1fgoogle/protobuf/timestamp.proto"\x91\x02\n\tEventInfo\x12\x0c\n\x04name\x18\x01 \x01(\t\x12\x0c\n\x04\x63ode\x18\x02 \x01(\t\x12\x0b\n\x03msg\x18\x03 \x01(\t\x12\r\n\x05level\x18\x04 \x01(\t\x12\x15\n\rinvocation_id\x18\x05 \x01(\t\x12\x0b\n\x03pid\x18\x06 \x01(\x05\x12\x0e\n\x06thread\x18\x07 \x01(\t\x12&\n\x02ts\x18\x08 \x01(\x0b\x32\x1a.google.protobuf.Timestamp\x12\x30\n\x05\x65xtra\x18\t \x03(\x0b\x32!.proto_types.EventInfo.ExtraEntry\x12\x10\n\x08\x63\x61tegory\x18\n \x01(\t\x1a,\n\nExtraEntry\x12\x0b\n\x03key\x18\x01 \x01(\t\x12\r\n\x05value\x18\x02 \x01(\t:\x02\x38\x01"6\n\x0eGenericMessage\x12$\n\x04info\x18\x01 \x01(\x0b\x32\x16.proto_types.EventInfo"1\n\x11RetryExternalCall\x12\x0f\n\x07\x61ttempt\x18\x01 \x01(\x05\x12\x0b\n\x03max\x18\x02 \x01(\x05"j\n\x14RetryExternalCallMsg\x12$\n\x04info\x18\x01 \x01(\x0b\x32\x16.proto_types.EventInfo\x12,\n\x04\x64\x61ta\x18\x02 \x01(\x0b\x32\x1e.proto_types.RetryExternalCall"#\n\x14RecordRetryException\x12\x0b\n\x03\x65xc\x18\x01 \x01(\t"p\n\x17RecordRetryExceptionMsg\x12$\n\x04info\x18\x01 \x01(\x0b\x32\x16.proto_types.EventInfo\x12/\n\x04\x64\x61ta\x18\x02 \x01(\x0b\x32!.proto_types.RecordRetryException"@\n\x13SystemCouldNotWrite\x12\x0c\n\x04path\x18\x01 \x01(\t\x12\x0e\n\x06reason\x18\x02 \x01(\t\x12\x0b\n\x03\x65xc\x18\x03 \x01(\t"n\n\x16SystemCouldNotWriteMsg\x12$\n\x04info\x18\x01 \x01(\x0b\x32\x16.proto_types.EventInfo\x12.\n\x04\x64\x61ta\x18\x02 \x01(\x0b\x32 .proto_types.SystemCouldNotWrite"!\n\x12SystemExecutingCmd\x12\x0b\n\x03\x63md\x18\x01 \x03(\t"l\n\x15SystemExecutingCmdMsg\x12$\n\x04info\x18\x01 \x01(\x0b\x32\x16.proto_types.EventInfo\x12-\n\x04\x64\x61ta\x18\x02 \x01(\x0b\x32\x1f.proto_types.SystemExecutingCmd"\x1c\n\x0cSystemStdOut\x12\x0c\n\x04\x62msg\x18\x01 \x01(\t"`\n\x0fSystemStdOutMsg\x12$\n\x04info\x18\x01 \x01(\x0b\x32\x16.proto_types.EventInfo\x12\'\n\x04\x64\x61ta\x18\x02 \x01(\x0b\x32\x19.proto_types.SystemStdOut"\x1c\n\x0cSystemStdErr\x12\x0c\n\x04\x62msg\x18\x01 \x01(\t"`\n\x0fSystemStdErrMsg\x12$\n\x04info\x18\x01 \x01(\x0b\x32\x16.proto_types.EventInfo\x12\'\n\x04\x64\x61ta\x18\x02 \x01(\x0b\x32\x19.proto_types.SystemStdErr",\n\x16SystemReportReturnCode\x12\x12\n\nreturncode\x18\x01 \x01(\x05"t\n\x19SystemReportReturnCodeMsg\x12$\n\x04info\x18\x01 \x01(\x0b\x32\x16.proto_types.EventInfo\x12\x31\n\x04\x64\x61ta\x18\x02 \x01(\x0b\x32#.proto_types.SystemReportReturnCode"\x19\n\nFormatting\x12\x0b\n\x03msg\x18\x01 \x01(\t"\\\n\rFormattingMsg\x12$\n\x04info\x18\x01 \x01(\x0b\x32\x16.proto_types.EventInfo\x12%\n\x04\x64\x61ta\x18\x02 \x01(\x0b\x32\x17.proto_types.Formatting"\x13\n\x04Note\x12\x0b\n\x03msg\x18\x01 \x01(\t"P\n\x07NoteMsg\x12$\n\x04info\x18\x01 \x01(\x0b\x32\x16.proto_types.EventInfo\x12\x1f\n\x04\x64\x61ta\x18\x02 \x01(\x0b\x32\x11.proto_types.Noteb\x06proto3'
)

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, "common_types_pb2", _globals)
if _descriptor._USE_C_DESCRIPTORS == False:
    DESCRIPTOR._options = None
    _EVENTINFO_EXTRAENTRY._options = None
    _EVENTINFO_EXTRAENTRY._serialized_options = b"8\001"
    _globals["_EVENTINFO"]._serialized_start = 69
    _globals["_EVENTINFO"]._serialized_end = 342
    _globals["_EVENTINFO_EXTRAENTRY"]._serialized_start = 298
    _globals["_EVENTINFO_EXTRAENTRY"]._serialized_end = 342
    _globals["_GENERICMESSAGE"]._serialized_start = 344
    _globals["_GENERICMESSAGE"]._serialized_end = 398
    _globals["_RETRYEXTERNALCALL"]._serialized_start = 400
    _globals["_RETRYEXTERNALCALL"]._serialized_end = 449
    _globals["_RETRYEXTERNALCALLMSG"]._serialized_start = 451
    _globals["_RETRYEXTERNALCALLMSG"]._serialized_end = 557
    _globals["_RECORDRETRYEXCEPTION"]._serialized_start = 559
    _globals["_RECORDRETRYEXCEPTION"]._serialized_end = 594
    _globals["_RECORDRETRYEXCEPTIONMSG"]._serialized_start = 596
    _globals["_RECORDRETRYEXCEPTIONMSG"]._serialized_end = 708
    _globals["_SYSTEMCOULDNOTWRITE"]._serialized_start = 710
    _globals["_SYSTEMCOULDNOTWRITE"]._serialized_end = 774
    _globals["_SYSTEMCOULDNOTWRITEMSG"]._serialized_start = 776
    _globals["_SYSTEMCOULDNOTWRITEMSG"]._serialized_end = 886
    _globals["_SYSTEMEXECUTINGCMD"]._serialized_start = 888
    _globals["_SYSTEMEXECUTINGCMD"]._serialized_end = 921
    _globals["_SYSTEMEXECUTINGCMDMSG"]._serialized_start = 923
    _globals["_SYSTEMEXECUTINGCMDMSG"]._serialized_end = 1031
    _globals["_SYSTEMSTDOUT"]._serialized_start = 1033
    _globals["_SYSTEMSTDOUT"]._serialized_end = 1061
    _globals["_SYSTEMSTDOUTMSG"]._serialized_start = 1063
    _globals["_SYSTEMSTDOUTMSG"]._serialized_end = 1159
    _globals["_SYSTEMSTDERR"]._serialized_start = 1161
    _globals["_SYSTEMSTDERR"]._serialized_end = 1189
    _globals["_SYSTEMSTDERRMSG"]._serialized_start = 1191
    _globals["_SYSTEMSTDERRMSG"]._serialized_end = 1287
    _globals["_SYSTEMREPORTRETURNCODE"]._serialized_start = 1289
    _globals["_SYSTEMREPORTRETURNCODE"]._serialized_end = 1333
    _globals["_SYSTEMREPORTRETURNCODEMSG"]._serialized_start = 1335
    _globals["_SYSTEMREPORTRETURNCODEMSG"]._serialized_end = 1451
    _globals["_FORMATTING"]._serialized_start = 1453
    _globals["_FORMATTING"]._serialized_end = 1478
    _globals["_FORMATTINGMSG"]._serialized_start = 1480
    _globals["_FORMATTINGMSG"]._serialized_end = 1572
    _globals["_NOTE"]._serialized_start = 1574
    _globals["_NOTE"]._serialized_end = 1593
    _globals["_NOTEMSG"]._serialized_start = 1595
    _globals["_NOTEMSG"]._serialized_end = 1675
# @@protoc_insertion_point(module_scope)
