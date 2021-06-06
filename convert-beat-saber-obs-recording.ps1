[CmdletBinding(DefaultParameterSetName='noOutPath')]
param (
    # Starting timestamp
    [Parameter(Mandatory=$true)]
    [string]$start,
    # Ending timestamp
    [string]$end,
    # Source file
    [Parameter(Mandatory=$true)]
    [string]$path,
    # Target file
    [parameter(ParameterSetName='haveOutPath')]
    [string]$outPath,
    # Target directory
    [parameter(ParameterSetName='noOutPathWithBsr')]
    [parameter(ParameterSetName='noOutPathNoBsr')]
    [string]$outDir = '.',
    # Date (guess if not provided)
    [parameter(ParameterSetName='noOutPathWithBsr')]
    [parameter(ParameterSetName='noOutPathNoBsr')]
    [ValidatePattern('^\d{4}-\d{2}-\d{2}$')]
    [string]$date,
    # Hour (guess if not provided)
    [parameter(ParameterSetName='noOutPathWithBsr')]
    [parameter(ParameterSetName='noOutPathNoBsr')]
    [ValidatePattern('^\d{2}$')]
    [string]$time,
    # BSR ID
    [parameter(ParameterSetName='noOutPathWithBsr', Mandatory=$true)]
    [ValidatePattern('^[0-9a-fA-F]+$')]
    [string]$bsrId,
    # Artist
    [parameter(ParameterSetName='noOutPathNoBsr')]
    [string]$artist,
    # Mapper
    [parameter(ParameterSetName='noOutPathNoBsr')]
    [string]$mapper,
    # Song
    [Parameter(ParameterSetName='noOutPathNoBsr', Mandatory=$true)]
    [string]$song,
    # Level type
    [parameter(ParameterSetName='noOutPathWithBsr', Mandatory=$true)]
    [parameter(ParameterSetName='noOutPathNoBsr', Mandatory=$true)]
    [ValidatePattern('^(((90|360)°|Lawless|Lightshow|No Arrows|One Handed) )?(Easy|Normal|Hard|Expert\+?)$')]
    [string]$difficulty,
    # Misses
    [parameter(ParameterSetName='noOutPathWithBsr', Mandatory=$true)]
    [parameter(ParameterSetName='noOutPathNoBsr', Mandatory=$true)]
    [int]$misses,
    # Rank
    [parameter(ParameterSetName='noOutPathWithBsr', Mandatory=$true)]
    [parameter(ParameterSetName='noOutPathNoBsr', Mandatory=$true)]
    [ValidatePattern('^([A-F]|S{1,3})$')]
    [string]$rank,
    # Modifiers
    # - Score-impacting modifiers:
    #   - DA - Disappearing Arrows
    #   - FS - Faster Song
    #   - GN - Ghost Notes
    #   - NA - No Arrows
    #   - NB - No Bombs
    #   - NW - No Walls
    #   - SFS - Super Fast Song
    #   - SS - Slower Song
    # - Sometimes score-impacting modifiers
    #   - NF - No Fail TODO
    # - Non-score-impacting modifiers:
    #   - 1L - 1 Life
    #   - 4L - 4 Lives
    #   - SA - Strict Angles
    #   - SN - Small Notes
    #   - PM - Pro Mode
    #   - ZM - Zen Mode
    # - Player settings:
    #   - LH - Left Handed
    #   - SL - Static Lights
    [parameter(ParameterSetName='noOutPathWithBsr')]
    [parameter(ParameterSetName='noOutPathNoBsr')]
    [ValidatePattern('^([14L]|DA|FS|GN|LH|N[ABFW]|PM|S([ALNS]|FS)|ZM)$')]
    [string[]]$modifiers,
    [parameter(ParameterSetName='noOutPathWithBsr')]
    [parameter(ParameterSetName='noOutPathNoBsr')]
    [string]$comment
)

$ErrorActionPreference = 'Stop'

Set-Variable `
    -Name InvalidFileNameRegex `
    -Option Constant `
    -Value "[$([regex]::Escape(([IO.Path]::GetInvalidFileNameChars() -join '')))]"

###

Add-Type `
    -Name Native `
    -Namespace $null `
    -MemberDefinition @"
[StructLayout(LayoutKind.Sequential)]
public struct BY_HANDLE_FILE_INFORMATION
{
    public UInt32 FileAttributes;
    public System.Runtime.InteropServices.ComTypes.FILETIME CreationTime;
    public System.Runtime.InteropServices.ComTypes.FILETIME LastAccessTime;
    public System.Runtime.InteropServices.ComTypes.FILETIME LastWriteTime;
    public UInt32 VolumeSerialNumber;
    public UInt32 FileSizeHigh;
    public UInt32 FileSizeLow;
    public UInt32 NumberOfLinks;
    public UInt32 FileIndexHigh;
    public UInt32 FileIndexLow;
};

[DllImport("kernel32.dll", SetLastError = true)]
private static extern bool GetFileInformationByHandle(IntPtr hFile, out BY_HANDLE_FILE_INFORMATION lpFileInformation);

public static BY_HANDLE_FILE_INFORMATION GetFileInformation(string path) {
    using (var f = System.IO.File.OpenRead(path)) {
        BY_HANDLE_FILE_INFORMATION info;
        GetFileInformationByHandle(f.SafeFileHandle.DangerousGetHandle(), out info);
        return info;
    }
}
"@

function Test-PathsEqual {
    [CmdletBinding()]
    param (
        [string]$path1,
        [string]$path2
    )

    try {
        $info1 = [Native]::GetFileInformation((Resolve-Path -LiteralPath $path1).Path)
        $info2 = [Native]::GetFileInformation((Resolve-Path -LiteralPath $path2).Path)

        return $info1.VolumeSerialNumber -eq $info2.VolumeSerialNumber -and
                $info1.FileIndexLow -eq $info2.FileIndexLow -and
                $info1.FileIndexHigh -eq $info2.FileIndexHigh
    } catch [System.Management.Automation.ItemNotFoundException] {
        return $false
    }
}

###

if (!$outPath) {
    $baseName = Split-Path -Path $path -Leaf

    if ($baseName -match '^(\d{4}-\d{2}-\d{2})\s*-?\s*(\d{2})') {
        $date = $matches[1]
        $time = $matches[2]
    }

    if (!$date -or !$time) {
        throw 'Date or time not provided and could not be determined from input filename'
    }

    if ($bsrId) {
        $data = Invoke-RestMethod `
            -Uri "https://beatsaver.com/api/maps/detail/${bsrId}" `
            -Headers @{'User-Agent' = 'convert-beat-saber-obs-recording/0.0 (https://github.com/chenxiaolong/random-scripts/blob/master/convert-beat-saber-obs-recording.ps1)'}

        function CleanUp($str) {
            if ($str) {
                $str = $str.Trim()
                while ($str -match '^(?:\(.*\)|\[.*\]|\{.*\})$') {
                    $str = $str.Substring(1, $str.Length - 2).Trim();
                }
            }
            return $str
        }

        $song = CleanUp($data.metadata.songName)
        $subName = CleanUp($data.metadata.songSubName)
        if ($subName) {
            $song += " ($subName)"
        }

        $artist = CleanUp($data.metadata.songAuthorName)
        $mapper = CleanUp($data.metadata.levelAuthorName)
    }

    $components = New-Object System.Collections.ArrayList
    $components.Add($date) | Out-Null
    $components.Add($time) | Out-Null

    $artistStr = ''

    if ($artist) {
        $artistStr += $artist
    }
    if ($mapper) {
        if ($artistStr) {
            $artistStr += ' '
        }
        $artistStr += "[$mapper]"
    }
    if ($artistStr) {
        $components.Add($artistStr) | Out-Null
    }

    $components.Add($song) | Out-Null

    $difficultyStr = $difficulty
    if ($modifiers) {
        $difficultyStr += " - $(($modifiers | Sort-Object) -join ', ')"
    }

    $components.Add($difficultyStr) | Out-Null

    $missesStr = switch ($misses) {
        { $_ -lt 0 } { 'Failed' }
        0 { 'Full Combo' }
        1 { '1 miss' }
        default { "$_ misses" }
    }

    $components.Add($missesStr) | Out-Null
    $components.Add($rank) | Out-Null

    if ($comment) {
        $components.Add($comment) | Out-Null
    }

    $filename = "$($components -join ' - ').mkv" -replace $InvalidFileNameRegex, '_'
    $outPath = Join-Path $outDir $filename
}

if (Test-PathsEqual $path $outPath) {
    throw 'Input and output paths are the same'
}

$timestampArgs = @('-ss', $start)
if ($end) {
    $timestampArgs += @('-to', $end)
}

$args =
    $timestampArgs +
    @(
        '-i', $path,
        '-c', 'copy',
        '-avoid_negative_ts', '1',
        $outPath
    )

ffmpeg.exe @args
exit $LASTEXITCODE
