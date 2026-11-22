# Nietzsche 局域网文件共享

目标文件夹：`C:\Users\cg\Desktop\Nietzsche`。

当前状态：**已启用，并通过本机实际 SMB 读写验证**。2026-11-03 已创建专用账户和共享，仅允许 `192.168.2.0/24` 网段连接。验证通过时间为2026-11-03 21:06:50（北京时间），具体结果见任务目录的 `verification.json`。尚未从第二台局域网设备实测。

## 在本机查看登录账户与密码

1. 在资源管理器打开：`C:\Users\cg\Desktop\Nietzsche\obsidian\NOESIS\tmp\nietzsche_lan_share`。
2. 双击 `Start-NietzscheShare.cmd`。
3. 当前已经配置完成，启动器会跳过创建步骤，再次检查读写能力。
4. 等待显示 `SHARING READY - AUTHENTICATED FILE OPERATIONS VERIFIED`。窗口会显示共享账户和随机密码，请保存密码。只有尚未配置时才需要 Windows 管理员授权。

已创建标准账户 `NietzscheLAN`，授予目标文件夹及继承权限的子文件读写、修改、拷贝、重命名和删除权限；该账户不允许在本机桌面或远程桌面登录。`cg` 的密码未作改动。

当前物理以太网已设为专用网络，新增规则仅允许 `192.168.2.0/24` 网段通过该网卡连接 SMB TCP 445，保留了现有 SMB 安全配置。详细配置结果保存在 `result.json`。

## 连接方式

- Windows：在资源管理器地址栏输入 `\\192.168.2.217\Nietzsche`，选择使用其他账户，输入窗口显示的账户和密码。
- macOS：Finder → 前往 → 连接服务器，输入 `smb://192.168.2.217/Nietzsche`，选择注册用户。
- iPhone/iPad：“文件”应用 → 连接服务器，输入 `smb://192.168.2.217`，选择注册用户后打开 `Nietzsche`。
- Android：使用支持 SMB 2/3 的文件管理器，服务器填 `192.168.2.217`，共享名填 `Nietzsche`，使用专用账户登录。

账户用户名为 `DESKTOP-S30CLNN\NietzscheLAN`。若客户端将计算机名与用户名分开填写，计算机/域填 `DESKTOP-S30CLNN`，用户名填 `NietzscheLAN`。

IP 是当前地址，若路由器以后重新分配地址，需要以本机新的局域网地址连接。

验证步骤只在这台电脑上通过专用账户连接实际 SMB 共享，测试创建、读取、编辑、拷贝、重命名与删除测试文件，并清理测试内容；尚未从第二台局域网设备验证连通性。

加密凭据暂存在任务目录的 `credential.xml`，使用当前 Windows 用户的 DPAPI 加密，未在脚本中保存明文密码。配置完成后如忘记密码，可由本机 `cg` 账户运行启动器重新显示。
