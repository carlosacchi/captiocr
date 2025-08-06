# Version Utilities for CaptiOCR

function Format-WixVersion {
    <#
    .SYNOPSIS
    Converts a semantic version to a WiX-compatible 4-part version number.
    
    .DESCRIPTION
    Transforms versions like 'v0.6.0-alpha' to '0.6.0.0' for WiX installer compatibility.
    
    .PARAMETER SemVer
    The semantic version string to convert.
    
    .EXAMPLE
    Format-WixVersion -SemVer "v0.6.0-alpha"
    # Returns: 0.6.0.0
    
    .EXAMPLE
    Format-WixVersion -SemVer "1.2"
    # Returns: 1.2.0.0
    #>
    [CmdletBinding()]
    param (
        [Parameter(Mandatory=$true)]
        [string]$SemVer
    )

    # Remove 'v' prefix and pre-release tags
    $cleanVersion = $SemVer -replace '^v', '' -replace '-.*$', ''

    # Split the version into parts
    $parts = $cleanVersion -split '\.'

    # Ensure we have at least 3 parts, pad with 0 if needed
    while ($parts.Length -lt 3) {
        $parts += '0'
    }

    # Add fourth part (build number) if not present
    if ($parts.Length -lt 4) {
        $parts += '0'
    }

    # Truncate to first 4 parts and validate each part is a valid integer
    $formattedParts = $parts[0..3] | ForEach-Object {
        try {
            [int]$_
        } catch {
            0  # Default to 0 if conversion fails
        }
    }

    # Ensure each part is within valid range (0-65534)
    $formattedParts = $formattedParts | ForEach-Object {
        [Math]::Min([Math]::Max($_, 0), 65534)
    }

    # Join back into dot-separated version
    return $formattedParts -join '.'
}

function Get-VersionFromGitTag {
    <#
    .SYNOPSIS
    Extracts version from git tag or current branch name.
    
    .DESCRIPTION
    Attempts to retrieve the version from git tags or branch name.
    
    .EXAMPLE
    Get-VersionFromGitTag
    # Returns the current version based on git context
    #>
    try {
        # Try to get version from git tag
        $tag = git describe --tags --abbrev=0 2>$null
        if ($tag) {
            return $tag
        }

        # Fallback to branch name
        $branch = git rev-parse --abbrev-ref HEAD 2>$null
        return $branch
    }
    catch {
        # Fallback to a default version if git commands fail
        return "v0.0.1"
    }
}

# If the script is run directly, demonstrate usage
if ($MyInvocation.InvocationName -eq '.') {
    $version = Get-VersionFromGitTag
    $wixVersion = Format-WixVersion -SemVer $version
    Write-Host "Git Version: $version"
    Write-Host "WiX Version: $wixVersion"
}