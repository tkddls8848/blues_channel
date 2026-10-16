param(
    [string]$BlenderExecutable = '',
    [switch]$EncodeOnly,
    [ValidateSet(1,2)][int]$Revision = 2
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$revisionName = if ($Revision -eq 2) { 'blender-duel-v2' } else { 'blender-duel' }
$durationSeconds = if ($Revision -eq 2) { 35 } else { 22 }
$songStartSeconds = if ($Revision -eq 2) { 155 } else { 168 }
$frameCount = $durationSeconds * 24
$scriptName = if ($Revision -eq 2) { 'blender_duel_v2.py' } else { 'blender_duel.py' }
$outputDirectory = Join-Path $projectRoot ('renders\' + $revisionName)
$audioFile = Join-Path $projectRoot ('assets\audio\bakkuo-' + $songStartSeconds + '-190.wav')
if (-not $BlenderExecutable) {
    $BlenderExecutable = Join-Path $projectRoot '.tools\blender\blender-4.5.9-windows-x64\blender.exe'
}
if (-not (Test-Path -LiteralPath $audioFile)) {
    $audioSource = Join-Path $projectRoot 'assets\audio\bakkuo-source.webm'
    if (-not (Test-Path -LiteralPath $audioSource)) { throw 'The locally provided song source is missing.' }
    & ffmpeg -hide_banner -loglevel error -y -ss $songStartSeconds -i $audioSource -t $durationSeconds -ar 48000 -ac 2 $audioFile
    if ($LASTEXITCODE -ne 0) { throw 'Audio extraction failed.' }
}
if (-not $EncodeOnly) {
    if (-not (Test-Path -LiteralPath $BlenderExecutable)) { throw 'Blender executable is missing.' }
    & $BlenderExecutable --background --factory-startup --python-exit-code 1 --python (Join-Path $PSScriptRoot $scriptName) -- --preview
    if ($LASTEXITCODE -ne 0) { throw 'Blender scene build failed.' }
    $sceneName = if ($Revision -eq 2) { 'bakkuo-ink-duel-v2.blend' } else { 'bakkuo-ink-duel.blend' }
    $sceneFile = Join-Path $outputDirectory $sceneName
    if ($Revision -eq 2) {
        & $BlenderExecutable --background $sceneFile --python-exit-code 1 --python (Join-Path $PSScriptRoot 'audit_blender_duel.py')
        if ($LASTEXITCODE -ne 0) { throw 'Blender limb reach audit failed.' }
    }
    & $BlenderExecutable --background $sceneFile --render-output (Join-Path $outputDirectory 'frames\frame-') --render-format PNG --frame-start 1 --frame-end $frameCount --render-anim
    if ($LASTEXITCODE -ne 0) { throw 'Blender render failed.' }
}
foreach ($frame in 1..$frameCount) {
    $frameFile = Join-Path $outputDirectory ('frames\frame-{0:0000}.png' -f $frame)
    if (-not (Test-Path -LiteralPath $frameFile)) { throw "Missing frame: $frame" }
}
$videoName = if ($Revision -eq 2) { 'bakkuo-blender-v2-155-190.mp4' } else { 'bakkuo-blender-animatic.mp4' }
$videoFile = Join-Path $outputDirectory $videoName
& ffmpeg -hide_banner -loglevel error -y -framerate 24 -start_number 1 -i (Join-Path $outputDirectory 'frames\frame-%04d.png') -i $audioFile -map 0:v:0 -map 1:a:0 -frames:v $frameCount -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -c:a aac -b:a 192k -t $durationSeconds -movflags +faststart $videoFile
if ($LASTEXITCODE -ne 0) { throw 'Video encoding failed.' }
$probeText = & ffprobe -v error -count_frames -show_entries 'format=duration:stream=codec_name,codec_type,width,height,r_frame_rate,nb_read_frames,duration' -of json $videoFile
if ($LASTEXITCODE -ne 0) { throw 'Video inspection failed.' }
$probe = ($probeText -join "`n") | ConvertFrom-Json
$videoStream = $probe.streams | Where-Object { $_.codec_type -eq 'video' }
$audioStream = $probe.streams | Where-Object { $_.codec_type -eq 'audio' }
if ($videoStream.width -ne 960 -or $videoStream.height -ne 540 -or [int]$videoStream.nb_read_frames -ne $frameCount -or $videoStream.r_frame_rate -ne '24/1') { throw 'Unexpected video dimensions or frame count.' }
if (-not $audioStream -or [Math]::Abs([double]$probe.format.duration - $durationSeconds) -gt 0.05) { throw 'Unexpected audio or duration.' }
& ffmpeg -hide_banner -loglevel error -i $videoFile -f null -
if ($LASTEXITCODE -ne 0) { throw 'Video failed a full decode.' }
$probe | Add-Member -NotePropertyName status -NotePropertyValue 'verified'
$probe | Add-Member -NotePropertyName additional_video_api_cost_usd -NotePropertyValue 0
$probe | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $outputDirectory 'verification.json') -Encoding UTF8
Write-Output $videoFile
