Dim shell, fso, projectRoot, pythonCandidate, pythonwCandidate, command

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

projectRoot = fso.GetParentFolderName(WScript.ScriptFullName)
pythonCandidate = shell.ExpandEnvironmentStrings("%PYTHON_BIN%")

If pythonCandidate = "%PYTHON_BIN%" Then
  pythonCandidate = ""
End If

pythonwCandidate = ""
If pythonCandidate <> "" Then
  If LCase(Right(pythonCandidate, 10)) = "python.exe" Then
    pythonwCandidate = Left(pythonCandidate, Len(pythonCandidate) - 10) & "pythonw.exe"
  Else
    pythonwCandidate = pythonCandidate
  End If
End If

If pythonwCandidate = "" Or Not fso.FileExists(pythonwCandidate) Then
  pythonwCandidate = "C:\Users\mingual\AppData\Local\Programs\Python\Python312\pythonw.exe"
End If

If Not fso.FileExists(pythonwCandidate) Then
  pythonwCandidate = "pythonw.exe"
End If

command = """" & pythonwCandidate & """ """ & fso.BuildPath(projectRoot, "jarvis_native.pyw") & """"
shell.Run command, 0, False
