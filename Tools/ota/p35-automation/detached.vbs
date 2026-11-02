Option Explicit
Dim service, startup, process, pid, result
If WScript.Arguments.Count <> 2 Then WScript.Quit 2
Set service = GetObject("winmgmts:\\.\root\cimv2")
Set startup = service.Get("Win32_ProcessStartup").SpawnInstance_
startup.ShowWindow = 0
Set process = service.Get("Win32_Process")
result = process.Create(WScript.Arguments(0), WScript.Arguments(1), startup, pid)
If result <> 0 Then
    WScript.StdOut.WriteLine "CREATE_ERROR=" & result
    WScript.Quit 2
End If
WScript.StdOut.WriteLine "PID=" & pid
