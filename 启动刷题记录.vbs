' 刷题记录系统 - 一键启动器
' 功能：检测服务是否已运行 -> 未运行则隐藏启动 Python 后端 -> 打开浏览器
Option Explicit
Dim shell, http, pyExe, cmd, i, ok, svcUrl
svcUrl = "http://127.0.0.1:8765/api/stats"
Set shell = CreateObject("WScript.Shell")

' 检测服务是否已就绪
Function ServiceReady()
  On Error Resume Next
  Dim h
  Set h = CreateObject("MSXML2.XMLHTTP")
  h.Open "GET", svcUrl, False
  h.Send
  ServiceReady = (h.Status = 200)
  On Error GoTo 0
End Function

If Not ServiceReady() Then
  ' 优先用 py 启动器，其次 python
  pyExe = "py -3"
  On Error Resume Next
  shell.Run pyExe & " --version", 0, True
  If Err.Number <> 0 Then
    pyExe = "python"
    Err.Clear
  End If
  On Error GoTo 0

  cmd = pyExe & " """ & Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\")) & "server.py"""
  ' 0 = 隐藏窗口, False = 不等待
  shell.Run cmd, 0, False

  ' 轮询等待服务起来，最多约 12 秒
  ok = False
  For i = 1 To 40
    WScript.Sleep 300
    If ServiceReady() Then
      ok = True
      Exit For
    End If
  Next
  If Not ok Then
    MsgBox "数据库服务启动失败。" & vbCrLf & vbCrLf & _
           "请确认已安装 Python，或手动运行：" & vbCrLf & cmd, _
           vbExclamation, "刷题记录"
    WScript.Quit 1
  End If
End If

' 打开浏览器
shell.Run "http://127.0.0.1:8765/", 1, False
