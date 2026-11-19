using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Web.Script.Serialization;
using System.Windows.Forms;

internal static class Dialogs {
    [DllImport("user32.dll")] private static extern bool SetForegroundWindow(IntPtr handle);
    [STAThread] private static int Main(string[] args) {
        if(args.Length==1 && args[0]=="--check") return System.Threading.Thread.CurrentThread.GetApartmentState()==System.Threading.ApartmentState.STA ? 0 : 3;
        var options=new Dictionary<string,string>();
        for(int i=0;i+1<args.Length;i+=2) options[args[i]]=args[i+1];
        string result;
        if(!options.TryGetValue("--result",out result)) return 2;
        try {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            string kind=options.ContainsKey("--kind")?options["--kind"]:"video";
            string directory=options.ContainsKey("--directory")?options["--directory"]:"";
            string name=options.ContainsKey("--name")?options["--name"]:"Vantage.mp4";
            var answer=new Dictionary<string,object>();
            answer["cancelled"]=true;
            using(var owner=new Form()) {
                owner.Text="Vantage"; owner.ShowInTaskbar=false; owner.TopMost=true;
                owner.Opacity=0; owner.Width=1; owner.Height=1;
                owner.StartPosition=FormStartPosition.CenterScreen;
                owner.Show(); owner.Activate(); SetForegroundWindow(owner.Handle);
                if(kind=="video" || kind=="frame") {
                    bool frame=kind=="frame";
                    using(var dialog=new SaveFileDialog()) {
                        dialog.Title=frame?"Vantage · 保存此帧":"Vantage · 导出视频另存为";
                        dialog.Filter=frame?"PNG 图片 (*.png)|*.png":"MP4 视频 (*.mp4)|*.mp4";
                        dialog.DefaultExt=frame?"png":"mp4"; dialog.AddExtension=true;
                        dialog.OverwritePrompt=true; dialog.CheckPathExists=true;
                        dialog.RestoreDirectory=true; dialog.FileName=Path.GetFileName(name);
                        if(Directory.Exists(directory)) dialog.InitialDirectory=directory;
                        if(dialog.ShowDialog(owner)==DialogResult.OK) {
                            answer["cancelled"]=false; answer["outputFile"]=dialog.FileName;
                            answer["overwrite"]=File.Exists(dialog.FileName);
                        }
                    }
                } else if(kind=="project") {
                    using(var dialog=new OpenFileDialog()) {
                        dialog.Title="Vantage · 打开工程";
                        dialog.Filter="Vantage 工程 (*.previs;*.zip;*.blend)|*.previs;*.zip;*.blend";
                        dialog.RestoreDirectory=true;
                        if(Directory.Exists(directory)) dialog.InitialDirectory=directory;
                        if(dialog.ShowDialog(owner)==DialogResult.OK) {
                            answer["cancelled"]=false; answer["file"]=dialog.FileName;
                        }
                    }
                } else if(kind=="directory") {
                    using(var dialog=new FolderBrowserDialog()) {
                        dialog.Description="Vantage · 选择工程保存文件夹";
                        dialog.ShowNewFolderButton=true;
                        if(Directory.Exists(directory)) dialog.SelectedPath=directory;
                        if(dialog.ShowDialog(owner)==DialogResult.OK) {
                            answer["cancelled"]=false; answer["directory"]=dialog.SelectedPath;
                        }
                    }
                } else throw new ArgumentException("未知保存窗口类型");
                owner.Close();
            }
            File.WriteAllText(result,new JavaScriptSerializer().Serialize(answer),new UTF8Encoding(false));
            return 0;
        } catch(Exception exc) {
            File.WriteAllText(result,new JavaScriptSerializer().Serialize(new {error=exc.Message}),new UTF8Encoding(false));
            return 1;
        }
    }
}
