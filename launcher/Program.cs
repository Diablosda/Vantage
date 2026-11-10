using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Windows.Forms;

[assembly: System.Reflection.AssemblyTitle("Vantage")]
[assembly: System.Reflection.AssemblyProduct("Vantage")]
internal static class Launcher {
    [STAThread] private static int Main(string[] args) {
        try {
            string root=AppDomain.CurrentDomain.BaseDirectory;
            string engine=Environment.GetEnvironmentVariable("PREVIS_BLENDER");
            if (String.IsNullOrWhiteSpace(engine)) engine=Path.GetFullPath(Path.Combine(root,"..","blender","blender-5.2.2-windows-x64","blender.exe"));
            if (!File.Exists(Path.Combine(root,"server.py")) || !File.Exists(Path.Combine(root,"web","index.html")))
                throw new FileNotFoundException("启动器必须放在完整的 Vantage 程序目录中。请勿只复制 EXE。 ");
            if (!File.Exists(engine)) throw new FileNotFoundException("找不到 Blender 引擎。请按产品说明安装 Blender 5.2.2，或设置 PREVIS_BLENDER 为 blender.exe 的完整路径。\n\n"+engine);
            string engineDir=Path.GetDirectoryName(Path.GetFullPath(engine));
            string python=Path.Combine(engineDir,"5.2","python","bin","python.exe");
            if (!File.Exists(python)) throw new FileNotFoundException("找不到 Blender 5.2 内置 Python，请检查 Blender 安装。\n\n"+python);
            if (!File.Exists(Path.Combine(root,"Vantage.Dialogs.exe"))) throw new FileNotFoundException("缺少 Vantage.Dialogs.exe，请保留完整的 Vantage 程序文件。 ");
            if (args.Contains("--check")) return 0;
            bool noOpen=args.Contains("--no-open");
            string parameters="-B -m server"+(noOpen?"":" --open");
            int port=Array.IndexOf(args,"--port");
            int value;
            if (port>=0 && port+1<args.Length && Int32.TryParse(args[port+1],out value) && value>0 && value<=65535) parameters+=" --port "+value;
            var start=new ProcessStartInfo(python,parameters) { WorkingDirectory=root, UseShellExecute=false, CreateNoWindow=true, WindowStyle=ProcessWindowStyle.Hidden };
            start.EnvironmentVariables["PREVIS_BLENDER"]=Path.GetFullPath(engine);
            start.EnvironmentVariables["PYTHONDONTWRITEBYTECODE"]="1";
            Process.Start(start);
            return 0;
        } catch (Exception exc) {
            MessageBox.Show("Vantage 未能启动：\n"+exc.Message,"Vantage",MessageBoxButtons.OK,MessageBoxIcon.Error);
            return 1;
        }
    }
}
