using System;
using System.Diagnostics;
using System.IO;
using System.Threading;

class Updater
{
    static string LogFile = Path.Combine(Path.GetTempPath(), "rm_updater.log");

    static void Log(string msg)
    {
        try { File.AppendAllText(LogFile, DateTime.Now.ToString("HH:mm:ss") + " " + msg + "\r\n"); }
        catch { }
    }

    static void Kill(string name)
    {
        try
        {
            string pn = Path.GetFileNameWithoutExtension(name);
            foreach (Process p in Process.GetProcessesByName(pn))
            {
                try { p.Kill(); p.WaitForExit(3000); } catch { }
            }
        }
        catch { }
    }

    static int Main(string[] args)
    {
        Log("start");
        try
        {
            if (args.Length < 2)
            {
                Log("bad args");
                return 2;
            }
            string installer = args[0];
            string target = args[1];
            Log("installer=" + installer + " target=" + target);

            Thread.Sleep(2000);
            Kill("RouterMaster.exe");
            Kill("RouterMasterAdmin.exe");
            Thread.Sleep(1000);

            if (!File.Exists(installer))
            {
                Log("installer not found");
                return 4;
            }

            Process p = Process.Start(new ProcessStartInfo
            {
                FileName = installer,
                Arguments = "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-",
                UseShellExecute = false
            });
            p.WaitForExit();
            Log("installer exit=" + p.ExitCode);
            if (p.ExitCode != 0)
            {
                Log("installer failed");
                return 1;
            }

            if (File.Exists(target))
            {
                Process.Start(new ProcessStartInfo
                {
                    FileName = "explorer.exe",
                    Arguments = "\"" + target + "\"",
                    UseShellExecute = false
                });
                Log("launched via explorer");
            }
            else
            {
                Log("target not found: " + target);
            }
            return 0;
        }
        catch (Exception e)
        {
            Log("error: " + e);
            return 3;
        }
    }
}
