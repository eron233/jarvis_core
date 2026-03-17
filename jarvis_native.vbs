Dim shell, fso, projectRoot, command, cmdHost

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

projectRoot = fso.GetParentFolderName(WScript.ScriptFullName)
cmdHost = shell.ExpandEnvironmentStrings("%ComSpec%")
If cmdHost = "%ComSpec%" Then
  cmdHost = "cmd.exe"
End If

command = """" & cmdHost & """ /c """ & fso.BuildPath(projectRoot, "jarvis.cmd") & """ native-app"
shell.Run command, 0, False
