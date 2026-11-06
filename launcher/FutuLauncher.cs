// 双击启动 futu_app.py：用 pythonw（不弹控制台），工作目录就是 exe 所在目录，项目复制到哪都能用。
// 重新编译：运行同目录下的 build.bat
using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Windows.Forms;

static class FutuLauncher
{
    const string Title = "富途牛牛";

    [STAThread]
    static int Main(string[] args)
    {
        string dir = AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\');
        string script = Path.Combine(dir, "futu_app.py");
        if (!File.Exists(script))
            return Fail("找不到 futu_app.py。\n请把本程序放在项目目录（和 futu_app.py 同一目录）里运行。");

        string python = FindPythonw(dir);
        if (python == null)
            return Fail("没有找到 Python（pythonw.exe）。\n请安装 Python 3，并执行：\npip install PyQt6 PyQt6-WebEngine");

        var psi = new ProcessStartInfo(python)
        {
            Arguments = Quote(script) + string.Concat(args.Select(a => " " + Quote(a))),
            WorkingDirectory = dir,
            UseShellExecute = false,
        };
        Process proc;
        try
        {
            proc = Process.Start(psi);
        }
        catch (Exception e)
        {
            return Fail("启动失败：" + python + "\n" + e.Message);
        }

        // 启动阶段（缺少 PyQt6 等）出错会很快退出，把日志末尾提示出来
        if (proc.WaitForExit(8000) && proc.ExitCode != 0)
        {
            string log = Path.Combine(dir, ".qt_profile", "app.log");
            string tail = "";
            try
            {
                if (File.Exists(log))
                    tail = string.Join("\n", File.ReadAllLines(log).Reverse().Take(12).Reverse());
            }
            catch (Exception e)
            {
                tail = "（读取日志失败：" + e.Message + "）";
            }
            return Fail("程序启动失败（退出码 " + proc.ExitCode + "）。\n\n" + tail +
                        "\n\n完整日志：" + log);
        }
        return 0;
    }

    static string FindPythonw(string dir)
    {
        // 1. 项目自带的虚拟环境
        foreach (var venv in new[] { ".venv", "venv" })
        {
            string p = Path.Combine(dir, venv, "Scripts", "pythonw.exe");
            if (File.Exists(p)) return p;
        }
        // 2. PATH 里的 pythonw.exe / python.exe 旁边的 pythonw.exe（跳过 WindowsApps 里的应用商店占位程序）
        var paths = (Environment.GetEnvironmentVariable("PATH") ?? "")
            .Split(';').Select(s => s.Trim().Trim('"')).Where(s => s.Length > 0
                && s.IndexOf("WindowsApps", StringComparison.OrdinalIgnoreCase) < 0);
        foreach (var p in paths)
        {
            try
            {
                string w = Path.Combine(p, "pythonw.exe");
                if (File.Exists(w)) return w;
            }
            catch (ArgumentException) { }
        }
        // 3. py 启动器
        string pyw = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Windows), "pyw.exe");
        return File.Exists(pyw) ? pyw : null;
    }

    static string Quote(string s)
    {
        return "\"" + s.Replace("\"", "\\\"") + "\"";
    }

    static int Fail(string message)
    {
        MessageBox.Show(message, Title, MessageBoxButtons.OK, MessageBoxIcon.Error);
        return 1;
    }
}
