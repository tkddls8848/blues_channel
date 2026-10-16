param([switch]$EncodeOnly)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
$outputDirectory=Join-Path $projectRoot 'renders\gp-animation'
$blenderExecutable=Join-Path $projectRoot '.tools\blender\blender-4.5.9-windows-x64\blender.exe'
if (-not $EncodeOnly) {
    & python (Join-Path $PSScriptRoot 'trace_duel_gp.py')
    if ($LASTEXITCODE -ne 0) { throw 'Vector preparation failed.' }
    & $blenderExecutable --background --factory-startup --python-exit-code 1 --python (Join-Path $PSScriptRoot 'animate_gp_duel.py') -- --render
    if ($LASTEXITCODE -ne 0) { throw 'Animation render failed.' }
}
foreach ($frame in 1..420) {
    if (-not (Test-Path -LiteralPath (Join-Path $outputDirectory ('frames\frame-{0:0000}.png' -f $frame)))) { throw "Missing animation drawing: $frame" }
}
$fullVideo=Join-Path $outputDirectory 'bakkuo-gp-155-190.mp4'
$combatVideo=Join-Path $outputDirectory 'bakkuo-gp-combat-170-190.mp4'
$audioFile=Join-Path $projectRoot 'assets\audio\bakkuo-155-190.wav'
& ffmpeg -hide_banner -loglevel error -y -framerate 12 -start_number 1 -i (Join-Path $outputDirectory 'frames\frame-%04d.png') -i $audioFile -map 0:v:0 -map 1:a:0 -vf fps=24 -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -c:a aac -b:a 192k -t 35 -movflags +faststart $fullVideo
if ($LASTEXITCODE -ne 0) { throw 'Full animation encoding failed.' }
& ffmpeg -hide_banner -loglevel error -y -ss 15 -i $fullVideo -t 20 -map 0:v:0 -map 0:a:0 -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -c:a aac -b:a 192k -movflags +faststart $combatVideo
if ($LASTEXITCODE -ne 0) { throw 'Combat excerpt encoding failed.' }
$results=@()
foreach ($entry in @(@($fullVideo,35,840),@($combatVideo,20,480))) {
    $probeText=& ffprobe -v error -count_frames -show_entries 'format=duration:stream=codec_name,codec_type,width,height,r_frame_rate,nb_read_frames' -of json $entry[0]
    if ($LASTEXITCODE -ne 0) { throw 'Video inspection failed.' }
    $probe=($probeText -join "`n") | ConvertFrom-Json
    $v=$probe.streams | Where-Object { $_.codec_type -eq 'video' }
    $a=$probe.streams | Where-Object { $_.codec_type -eq 'audio' }
    if ($v.width -ne 960 -or $v.height -ne 540 -or $v.r_frame_rate -ne '24/1' -or [int]$v.nb_read_frames -ne $entry[2] -or [Math]::Abs([double]$probe.format.duration-$entry[1]) -gt .05 -or -not $a) { throw 'Unexpected video stream or duration.' }
    & ffmpeg -hide_banner -loglevel error -i $entry[0] -f null -
    if ($LASTEXITCODE -ne 0) { throw 'Video decode failed.' }
    $results+=@{file=[IO.Path]::GetFileName($entry[0]);seconds=$entry[1];frames=$entry[2];width=$v.width;height=$v.height;status='verified'}
}
@{videos=$results;drawing_fps=12;output_fps=24;additional_api_cost_usd=0;technique='Illustrated cutout armatures with animated native Grease Pencil ink and weapons'} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $outputDirectory 'verification.json') -Encoding UTF8
Write-Output $combatVideo
Write-Output $fullVideo
