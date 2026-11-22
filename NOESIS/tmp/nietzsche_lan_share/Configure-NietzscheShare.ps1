param([Parameter(Mandatory=$true)][string]$WorkDir)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$resultPath = Join-Path $WorkDir 'result.json'
$backupPath = Join-Path $WorkDir 'before.json'
$targetPath = 'C:\Users\cg\Desktop\Nietzsche'
$shareName = 'Nietzsche'
$userName = 'NietzscheLAN'
$ruleName = 'Nietzsche-LAN-SMB-445'
$interfaceIndex = 14
$createdUser = $false
$createdShare = $false
$createdRule = $false
$changedAcl = $false
$changedProfile = $false
$before = $null

function Save-Result($value) {
    $value | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $resultPath -Encoding UTF8
}

try {
    $principal = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Windows administrator elevation was not granted.'
    }
    if ((Get-Item -LiteralPath $targetPath).FullName -ne $targetPath) { throw 'Unexpected target path.' }
    if (Get-SmbShare -Name $shareName -ErrorAction SilentlyContinue) { throw 'The share name is already in use; existing shares will not be replaced.' }
    if (Get-LocalUser -Name $userName -ErrorAction SilentlyContinue) { throw 'The dedicated account already exists; its password will not be changed.' }
    if (Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue) { throw 'The dedicated firewall rule already exists.' }

    $credential = Import-Clixml -LiteralPath (Join-Path $WorkDir 'credential.xml')
    $profile = Get-NetConnectionProfile -InterfaceIndex $interfaceIndex
    $adapter = Get-NetAdapter -InterfaceIndex $interfaceIndex
    $address = Get-NetIPAddress -InterfaceIndex $interfaceIndex -AddressFamily IPv4 | Where-Object { $_.AddressState -eq 'Preferred' -and $_.IPAddress -eq '192.168.2.217' }
    if (-not $adapter.HardwareInterface -or -not $address -or $address.PrefixLength -ne 24) { throw 'LAN interface changed; review the network before configuring sharing.' }
    $acl = Get-Acl -LiteralPath $targetPath
    $before = [ordered]@{
        Target = $targetPath
        NetworkInterfaceIndex = $interfaceIndex
        NetworkCategory = $profile.NetworkCategory.ToString()
        RootAclSddl = $acl.GetSecurityDescriptorSddlForm([Security.AccessControl.AccessControlSections]::All)
        CapturedAt = (Get-Date).ToString('o')
    }
    $before | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $backupPath -Encoding UTF8
    Save-Result @{ Status='running'; Step='Creating a dedicated standard account' }

    $user = New-LocalUser -Name $userName -Password $credential.Password -FullName 'Nietzsche LAN file sharing' -Description 'Nietzsche folder SMB access' -AccountNeverExpires -PasswordNeverExpires -UserMayNotChangePassword
    $createdUser = $true
    $usersGroup = Get-LocalGroup -SID 'S-1-5-32-545'
    if (-not (Get-LocalGroupMember -Group $usersGroup.Name | Where-Object { $_.SID -eq $user.SID })) {
        Add-LocalGroupMember -Group $usersGroup.Name -Member $user
    }
    $account = "$env:COMPUTERNAME\$userName"

    # Deny console and Remote Desktop logon for this account; network file logon remains allowed.
    Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
public static class NietzscheShareLogonPolicy {
  [StructLayout(LayoutKind.Sequential)] struct OBJECT_ATTRIBUTES {
    public int Length; public IntPtr RootDirectory; public IntPtr ObjectName; public uint Attributes;
    public IntPtr SecurityDescriptor; public IntPtr SecurityQualityOfService;
  }
  [StructLayout(LayoutKind.Sequential)] struct UNICODE_STRING {
    public ushort Length; public ushort MaximumLength; public IntPtr Buffer;
  }
  [DllImport("advapi32.dll")] static extern uint LsaOpenPolicy(IntPtr systemName, ref OBJECT_ATTRIBUTES attributes, uint access, out IntPtr handle);
  [DllImport("advapi32.dll")] static extern uint LsaAddAccountRights(IntPtr handle, byte[] sid, UNICODE_STRING[] rights, uint count);
  [DllImport("advapi32.dll")] static extern uint LsaClose(IntPtr handle);
  [DllImport("advapi32.dll")] static extern uint LsaNtStatusToWinError(uint status);
  public static void DenyInteractive(byte[] sid) {
    var attributes = new OBJECT_ATTRIBUTES(); attributes.Length = Marshal.SizeOf(attributes);
    IntPtr handle; uint status = LsaOpenPolicy(IntPtr.Zero, ref attributes, 0x00000810, out handle);
    if (status != 0) throw new Win32Exception((int)LsaNtStatusToWinError(status));
    string[] names = {"SeDenyInteractiveLogonRight", "SeDenyRemoteInteractiveLogonRight"};
    var rights = new UNICODE_STRING[names.Length];
    try {
      for (int i=0;i<names.Length;i++) {
        rights[i].Buffer=Marshal.StringToHGlobalUni(names[i]); rights[i].Length=(ushort)(names[i].Length*2); rights[i].MaximumLength=(ushort)(rights[i].Length+2);
      }
      status=LsaAddAccountRights(handle,sid,rights,(uint)rights.Length);
      if(status!=0) throw new Win32Exception((int)LsaNtStatusToWinError(status));
    } finally {
      foreach(var right in rights) if(right.Buffer!=IntPtr.Zero) Marshal.FreeHGlobal(right.Buffer);
      LsaClose(handle);
    }
  }
}
'@
    $sidBytes = New-Object byte[] $user.SID.BinaryLength
    $user.SID.GetBinaryForm($sidBytes,0)
    [NietzscheShareLogonPolicy]::DenyInteractive($sidBytes)

    Save-Result @{ Status='running'; Step='Granting folder and share permissions' }
    $accessRule = New-Object Security.AccessControl.FileSystemAccessRule($account, [Security.AccessControl.FileSystemRights]::Modify, ([Security.AccessControl.InheritanceFlags]::ContainerInherit -bor [Security.AccessControl.InheritanceFlags]::ObjectInherit), [Security.AccessControl.PropagationFlags]::None, [Security.AccessControl.AccessControlType]::Allow)
    $acl.AddAccessRule($accessRule)
    Set-Acl -LiteralPath $targetPath -AclObject $acl
    $changedAcl = $true
    if ((Get-Service LanmanServer).Status -ne 'Running') { Start-Service LanmanServer }
    New-SmbShare -Name $shareName -Path $targetPath -Description 'Nietzsche authenticated LAN read/write files' -ChangeAccess $account -FullAccess "$env:COMPUTERNAME\cg" -FolderEnumerationMode AccessBased -CachingMode None | Out-Null
    $createdShare = $true

    Save-Result @{ Status='running'; Step='Restricting SMB access to the physical LAN subnet' }
    if ($profile.NetworkCategory -eq 'Public') {
        Set-NetConnectionProfile -InterfaceIndex $interfaceIndex -NetworkCategory Private
        $changedProfile = $true
    }
    New-NetFirewallRule -Name $ruleName -DisplayName 'Nietzsche LAN file sharing (TCP 445)' -Description 'Authenticated Nietzsche SMB sharing; physical Ethernet, Private profile, 192.168.2.0/24 only.' -Direction Inbound -Action Allow -Enabled True -Profile Private -InterfaceAlias $adapter.Name -Protocol TCP -LocalPort 445 -RemoteAddress '192.168.2.0/24' -EdgeTraversalPolicy Block | Out-Null
    $createdRule = $true

    $share = Get-SmbShare -Name $shareName
    $shareAccess = Get-SmbShareAccess -Name $shareName | Select-Object AccountName,AccessControlType,AccessRight
    $server = Get-SmbServerConfiguration
    Save-Result ([ordered]@{
        Status='configured'
        ShareName=$shareName
        Path=$targetPath
        Server=$env:COMPUTERNAME
        IP='192.168.2.217'
        Subnet='192.168.2.0/24'
        UncPath='\\192.168.2.217\Nietzsche'
        Username=$account
        AccountSid=$user.SID.Value
        LocalAndRemoteDesktopLogon='Denied for the dedicated account'
        NetworkCategory=(Get-NetConnectionProfile -InterfaceIndex $interfaceIndex).NetworkCategory.ToString()
        ShareAccess=@($shareAccess)
        Smb1Enabled=$server.EnableSMB1Protocol
        Smb2Enabled=$server.EnableSMB2Protocol
        CompletedAt=(Get-Date).ToString('o')
    })
}
catch {
    $message = $_.Exception.Message
    $rollbackErrors = @()
    if ($createdRule) { try { Remove-NetFirewallRule -Name $ruleName } catch { $rollbackErrors += $_.Exception.Message } }
    if ($createdShare) { try { Remove-SmbShare -Name $shareName -Force } catch { $rollbackErrors += $_.Exception.Message } }
    if ($changedAcl -and $before) {
        try { $restoreAcl = Get-Acl -LiteralPath $targetPath; $restoreAcl.SetSecurityDescriptorSddlForm($before.RootAclSddl); Set-Acl -LiteralPath $targetPath -AclObject $restoreAcl } catch { $rollbackErrors += $_.Exception.Message }
    }
    if ($changedProfile -and $before) { try { Set-NetConnectionProfile -InterfaceIndex $interfaceIndex -NetworkCategory $before.NetworkCategory } catch { $rollbackErrors += $_.Exception.Message } }
    if ($createdUser) { try { Remove-LocalUser -Name $userName } catch { $rollbackErrors += $_.Exception.Message } }
    Save-Result @{Status='failed';Error=$message;RollbackErrors=$rollbackErrors}
    exit 1
}
