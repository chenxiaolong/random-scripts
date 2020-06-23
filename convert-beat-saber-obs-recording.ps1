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
    [parameter(ParameterSetName='noOutPath')]
    [string]$outDir = '.',
    # Date (guess if not provided)
    [parameter(ParameterSetName='noOutPath')]
    [ValidatePattern('^\d{4}-\d{2}-\d{2}$')]
    [string]$date,
    # Hour (guess if not provided)
    [parameter(ParameterSetName='noOutPath')]
    [ValidatePattern('^\d{2}$')]
    [string]$time,
    # Artist
    [Parameter(ParameterSetName='noOutPath')]
    [string]$artist,
    # Mapper
    [Parameter(ParameterSetName='noOutPath')]
    [string]$mapper,
    # Song
    [Parameter(ParameterSetName='noOutPath', Mandatory=$true)]
    [string]$song,
    # Level type
    [Parameter(ParameterSetName='noOutPath', Mandatory=$true)]
    [ValidatePattern('^(((90|360)°|One Handed) )?(Easy|Normal|Hard|Expert\+?)$')]
    [string]$difficulty,
    # Misses
    [Parameter(ParameterSetName='noOutPath', Mandatory=$true)]
    [int]$misses,
    # Rank
    [Parameter(ParameterSetName='noOutPath', Mandatory=$true)]
    [ValidatePattern('^([A-F]|S{1,3})$')]
    [string]$rank,
    # Modifiers
    # - Score-impacting modifiers:
    #   - DA - Disappearing Arrows
    #   - FS - Faster Song
    #   - GN - Ghost Notes
    #   - NA - No Arrows
    #   - NB - No Bombs
    #   - NF - No Fail
    #   - NO - No Obstacles
    #   - SS - Slower Song
    # - Non-score-impacting modifiers:
    #   - BE - Battery Energy
    #   - IF - Insta Fail
    # - Player settings:
    #   - LH - Left Handed
    #   - SL - Static Lights
    [Parameter(ParameterSetName='noOutPath')]
    [ValidatePattern('^(BE|DA|FS|GN|IF|LH|N[ABFO]|S[LS])$')]
    [string[]]$modifiers
)

$ErrorActionPreference = 'Stop'

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

    $difficultyStr = $difficulty
    if ($modifiers) {
        $difficultyStr += " - $(($modifiers | Sort-Object) -join ', ')"
    }

    $missesStr = switch ($misses) {
        { $_ -lt 0 } { 'Failed' }
        0 { 'Full Combo' }
        1 { '1 miss' }
        default { "$_ misses" }
    }

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
        $artistStr += ' - '
    }


    $outPath = Join-Path $outDir "$date - $time - $artistStr$song ($difficultyStr) - $missesStr - $rank.mkv"
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
