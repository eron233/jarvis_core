# Íris: instalação por usuário; inicia após execução voluntária do instalador.
# Um download NÃO executa programas automaticamente.
param([switch]$StartWithWindows, [switch]$ValidateOnly)
$ErrorActionPreference = "Stop"
$source = Split-Path -Parent $MyInvocation.MyCommand.Path
$binary = Join-Path $source "Genesis.exe"
$internal = Join-Path $source "_internal"
if (-not (Test-Path -LiteralPath $binary -PathType Leaf)) {
    throw "Genesis.exe não encontrado: extraia a pasta COMPLETA antes de instalar."
}
if (-not (Test-Path -LiteralPath $internal -PathType Container)) {
    throw "Arquivos internos ausentes: extraia a pasta COMPLETA."
}
if ($ValidateOnly) { Write-Output "Instalador validado; nenhuma instalação executada."; return }
$target = Join-Path $env:LOCALAPPDATA "Programs\GenesisIris"
if ([IO.Path]::GetFullPath($target).TrimEnd('\') -eq [IO.Path]::GetFullPath($source).TrimEnd('\')) {
    throw "Instalação já está no destino. Abra Genesis.exe diretamente."
}
New-Item -ItemType Directory -Path $target -Force | Out-Null
Copy-Item -Path (Join-Path $source "*") -Destination $target -Recurse -Force
$installed = Join-Path $target "Genesis.exe"
if (-not (Test-Path -LiteralPath $installed -PathType Leaf)) {
    throw "Cópia incompleta: executável indisponível."
}
$menuPath = Join-Path ([Environment]::GetFolderPath("Programs")) "Gênesis - Íris.lnk"
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($menuPath)
$shortcut.TargetPath = $installed
$shortcut.WorkingDirectory = $target
$shortcut.Arguments = "--mascot-only"
$shortcut.Description = "Íris, mascote visual do Gênesis"
$shortcut.Save()

# Inicio no login apenas quando usuario escolhe explicitamente.
if ($StartWithWindows) {
    $startupKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
    New-Item -Path $startupKey -Force | Out-Null
    $value = '"' + $installed + '" --mascot-only'
    New-ItemProperty -Path $startupKey -Name "GenesisIrisMascot" -Value $value -PropertyType String -Force | Out-Null
}
Write-Output "Íris instalada em $target"
Write-Output "Abrindo mascote Íris agora..."
Start-Process -FilePath $installed -ArgumentList "--mascot-only" -WorkingDirectory $target
