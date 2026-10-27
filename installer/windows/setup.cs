// ============================================================================
// CAT — Coding Agent Terminal Native Windows Setup Installer
// Compiled with Microsoft .NET Framework C# Compiler (csc.exe)
// Produces: CAT-Setup.exe and catsetup.exe
// ============================================================================

using System;
using System.Diagnostics;
using System.IO;
using System.Text;

namespace CatInstaller
{
    class Program
    {
        static int Main(string[] args)
        {
            bool silent = false;
            bool uninstall = false;
            string customInstallDir = null;

            for (int i = 0; i < args.Length; i++)
            {
                string a = args[i].ToLowerInvariant();
                if (a == "/s" || a == "-s" || a == "--silent" || a == "-q" || a == "--quiet")
                    silent = true;
                else if (a == "/u" || a == "-u" || a == "--uninstall")
                    uninstall = true;
                else if (a.StartsWith("/d=") || a.StartsWith("--dir="))
                    customInstallDir = args[i].Substring(args[i].IndexOf('=') + 1).Trim('"');
            }

            try
            {
                if (uninstall)
                {
                    return RunUninstall(silent, customInstallDir);
                }
                else
                {
                    return RunInstall(silent, customInstallDir);
                }
            }
            catch (Exception ex)
            {
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine("\n[ERROR] Installation failed: " + ex.Message);
                Console.ResetColor();
                if (!silent)
                {
                    Console.WriteLine("\nPress Enter to exit...");
                    Console.ReadLine();
                }
                return 1;
            }
        }

        static void PrintBanner(bool silent)
        {
            if (silent) return;
            Console.ForegroundColor = ConsoleColor.Cyan;
            Console.WriteLine("================================================================");
            Console.ForegroundColor = ConsoleColor.Magenta;
            Console.WriteLine("   CAT — Coding Agent Terminal (Native Windows Installer)");
            Console.ForegroundColor = ConsoleColor.DarkCyan;
            Console.WriteLine("   Version: 0.8.0b1 | Tokyo Night Edition");
            Console.ForegroundColor = ConsoleColor.Cyan;
            Console.WriteLine("================================================================\n");
            Console.ResetColor();
        }

        static string FindPython(out string version)
        {
            version = "3.10+";
            string[] commands = new string[] { "python.exe", "py.exe", "python3.exe" };
            foreach (string cmd in commands)
            {
                try
                {
                    ProcessStartInfo psi = new ProcessStartInfo(cmd, "-c \"import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}|{sys.executable}')\"")
                    {
                        RedirectStandardOutput = true,
                        RedirectStandardError = true,
                        UseShellExecute = false,
                        CreateNoWindow = true
                    };
                    using (Process p = Process.Start(psi))
                    {
                        string output = p.StandardOutput.ReadToEnd();
                        p.WaitForExit(4000);
                        if (p.ExitCode == 0 && output.Contains("|"))
                        {
                            string[] parts = output.Trim().Split('|');
                            string ver = parts[0];
                            string exe = parts[1];
                            string[] vParts = ver.Split('.');
                            if (vParts.Length >= 2)
                            {
                                int major = int.Parse(vParts[0]);
                                int minor = int.Parse(vParts[1]);
                                if (major >= 3 && minor >= 10)
                                {
                                    version = ver;
                                    return exe;
                                }
                            }
                        }
                    }
                }
                catch { }
            }

            // Check standard WindowsApps path
            string localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            string winApps = Path.Combine(localAppData, "Microsoft", "WindowsApps");
            if (Directory.Exists(winApps))
            {
                string pyApp = Path.Combine(winApps, "python.exe");
                if (File.Exists(pyApp))
                {
                    version = "3.12 (WindowsApps)";
                    return pyApp;
                }
            }

            return null;
        }

        static int RunInstall(bool silent, string customInstallDir)
        {
            PrintBanner(silent);

            string localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            string installDir = string.IsNullOrEmpty(customInstallDir)
                ? Path.Combine(localAppData, "Programs", "CAT")
                : customInstallDir;

            if (!silent)
            {
                Console.ForegroundColor = ConsoleColor.Yellow;
                Console.WriteLine("[1/5] Detecting Python 3.10+ runtime...");
                Console.ResetColor();
            }

            string pyVersion;
            string pyExe = FindPython(out pyVersion);
            if (string.IsNullOrEmpty(pyExe))
            {
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine("\n[ERROR] Python 3.10 or higher is required but was not found.");
                Console.WriteLine("Please install Python 3.10+ from: https://www.python.org/downloads/");
                Console.WriteLine("Or run in terminal: winget install Python.Python.3.12\n");
                Console.ResetColor();
                if (!silent)
                {
                    Console.WriteLine("Press Enter to exit...");
                    Console.ReadLine();
                }
                return 1;
            }

            if (!silent)
            {
                Console.ForegroundColor = ConsoleColor.Green;
                Console.WriteLine("      Found Python " + pyVersion + " at: " + pyExe);
                Console.ForegroundColor = ConsoleColor.Yellow;
                Console.WriteLine("[2/5] Creating installation directory structure...");
                Console.ResetColor();
            }

            string binDir = Path.Combine(installDir, "bin");
            string libDir = Path.Combine(installDir, "lib");
            Directory.CreateDirectory(binDir);
            Directory.CreateDirectory(libDir);

            if (!silent)
            {
                Console.ForegroundColor = ConsoleColor.Green;
                Console.WriteLine("      Target Directory: " + installDir);
                Console.ForegroundColor = ConsoleColor.Yellow;
                Console.WriteLine("[3/5] Deploying CAT CLI core modules...");
                Console.ResetColor();
            }

            // Look for adjacent or repository calc_terminal folder
            string exeDir = AppDomain.CurrentDomain.BaseDirectory;
            string[] possibleCalcDirs = new string[]
            {
                Path.Combine(exeDir, "calc_terminal"),
                Path.Combine(exeDir, "..", "calc_terminal"),
                Path.Combine(exeDir, "..", "..", "calc_terminal"),
                Path.Combine(exeDir, "..", "..", "..", "calc_terminal")
            };

            string foundCalc = null;
            foreach (string cand in possibleCalcDirs)
            {
                string fullCand = Path.GetFullPath(cand);
                if (Directory.Exists(fullCand) && File.Exists(Path.Combine(fullCand, "cli.py")))
                {
                    foundCalc = fullCand;
                    break;
                }
            }

            if (foundCalc != null)
            {
                string targetCalc = Path.Combine(libDir, "calc_terminal");
                CopyDirectory(foundCalc, targetCalc);
                if (!silent)
                {
                    Console.ForegroundColor = ConsoleColor.Green;
                    Console.WriteLine("      Synchronized core modules from: " + foundCalc);
                }
            }
            else
            {
                if (!silent)
                {
                    Console.ForegroundColor = ConsoleColor.DarkYellow;
                    Console.WriteLine("      Note: calc_terminal directory not found locally; falling back to environment python package.");
                }
            }

            if (!silent)
            {
                Console.ForegroundColor = ConsoleColor.Yellow;
                Console.WriteLine("[4/5] Generating launcher shims and developer commands...");
                Console.ResetColor();
            }

            // Write command launchers
            WriteShim(binDir, "cat.cmd", pyExe, "calc_terminal.cli");
            WriteShim(binDir, "catx.cmd", pyExe, "calc_terminal.cli");
            WriteShim(binDir, "cct.cmd", pyExe, "calc_terminal.cli");
            WriteShim(binDir, "cat-curl.cmd", pyExe, "calc_terminal.commands.curl_cmd");
            WriteShim(binDir, "cat-brew.cmd", pyExe, "calc_terminal.commands.brew_cmd");
            WriteShim(binDir, "cat-sudo.cmd", pyExe, "calc_terminal.commands.sudo_cmd");
            WritePs1Shim(binDir, "cat.ps1", pyExe);

            if (!silent)
            {
                Console.ForegroundColor = ConsoleColor.Green;
                Console.WriteLine("      Created commands in " + binDir + ":");
                Console.ForegroundColor = ConsoleColor.DarkCyan;
                Console.WriteLine("        - cat.cmd / cat.ps1       (CAT interactive launch)");
                Console.WriteLine("        - catx.cmd                (PowerShell collision-safe alias)");
                Console.WriteLine("        - cct.cmd                 (Classic alias)");
                Console.WriteLine("        - cat-curl.cmd            (Native HTTP/REST client)");
                Console.WriteLine("        - cat-brew.cmd            (Universal package bridge)");
                Console.WriteLine("        - cat-sudo.cmd            (Universal administrative elevation)");
                Console.ForegroundColor = ConsoleColor.Yellow;
                Console.WriteLine("[5/5] Updating User PATH and shell profiles...");
                Console.ResetColor();
            }

            // Update User PATH environment variable
            string userPath = Environment.GetEnvironmentVariable("Path", EnvironmentVariableTarget.User) ?? "";
            if (!userPath.ToLowerInvariant().Contains(binDir.ToLowerInvariant()))
            {
                string newPath = string.IsNullOrEmpty(userPath) ? binDir : (userPath.TrimEnd(';') + ";" + binDir);
                Environment.SetEnvironmentVariable("Path", newPath, EnvironmentVariableTarget.User);
                if (!silent)
                {
                    Console.ForegroundColor = ConsoleColor.Green;
                    Console.WriteLine("      Added " + binDir + " to User PATH.");
                }
            }

            // Configure PowerShell Profile alias helper
            try
            {
                string docsDir = Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments);
                string psDir = Path.Combine(docsDir, "WindowsPowerShell");
                string profilePath = Path.Combine(psDir, "Microsoft.PowerShell_profile.ps1");
                Directory.CreateDirectory(psDir);

                string aliasMarker = "# === CAT CLI Profile Integration ===";
                string existing = File.Exists(profilePath) ? File.ReadAllText(profilePath) : "";
                if (!existing.Contains(aliasMarker))
                {
                    StringBuilder sb = new StringBuilder();
                    sb.AppendLine();
                    sb.AppendLine(aliasMarker);
                    sb.AppendLine("if (Get-Command \"" + binDir + "\\cat.cmd\" -ErrorAction SilentlyContinue) {");
                    sb.AppendLine("    Remove-Item Alias:cat -Force -ErrorAction SilentlyContinue");
                    sb.AppendLine("    function global:cat { & \"" + binDir + "\\cat.cmd\" @args }");
                    sb.AppendLine("}");
                    sb.AppendLine("# ===================================");
                    File.AppendAllText(profilePath, sb.ToString());
                    if (!silent)
                    {
                        Console.ForegroundColor = ConsoleColor.Green;
                        Console.WriteLine("      Configured PowerShell profile alias helper.");
                    }
                }
            }
            catch { }

            if (!silent)
            {
                Console.ForegroundColor = ConsoleColor.Green;
                Console.WriteLine("\n================================================================");
                Console.WriteLine("   [SUCCESS] CAT CLI Setup Complete!");
                Console.WriteLine("================================================================\n");
                Console.ForegroundColor = ConsoleColor.Yellow;
                Console.WriteLine("You can now open a new terminal window and use CAT:");
                Console.ForegroundColor = ConsoleColor.Cyan;
                Console.WriteLine("  cat --version        # Display version");
                Console.WriteLine("  cat curl --version   # Test HTTP/REST curl client");
                Console.WriteLine("  cat brew doctor      # Check package manager status");
                Console.WriteLine("  cat sudo --status    # Check administrative elevation privileges");
                Console.WriteLine("  cat                  # Launch interactive Tokyo Night terminal\n");
                Console.ResetColor();

                Console.WriteLine("Press Enter to launch CAT CLI now (or close this window)...");
                string line = Console.ReadLine();
                try
                {
                    ProcessStartInfo startCat = new ProcessStartInfo(Path.Combine(binDir, "cat.cmd"))
                    {
                        UseShellExecute = true
                    };
                    Process.Start(startCat);
                }
                catch { }
            }

            return 0;
        }

        static int RunUninstall(bool silent, string customInstallDir)
        {
            PrintBanner(silent);
            string localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            string installDir = string.IsNullOrEmpty(customInstallDir)
                ? Path.Combine(localAppData, "Programs", "CAT")
                : customInstallDir;

            if (Directory.Exists(installDir))
            {
                Directory.Delete(installDir, true);
                if (!silent) Console.WriteLine("Removed directory: " + installDir);
            }

            string binDir = Path.Combine(installDir, "bin");
            string userPath = Environment.GetEnvironmentVariable("Path", EnvironmentVariableTarget.User) ?? "";
            if (userPath.ToLowerInvariant().Contains(binDir.ToLowerInvariant()))
            {
                string[] parts = userPath.Split(';');
                StringBuilder newPath = new StringBuilder();
                foreach (string p in parts)
                {
                    if (!string.IsNullOrEmpty(p) && !p.Equals(binDir, StringComparison.OrdinalIgnoreCase))
                    {
                        if (newPath.Length > 0) newPath.Append(";");
                        newPath.Append(p);
                    }
                }
                Environment.SetEnvironmentVariable("Path", newPath.ToString(), EnvironmentVariableTarget.User);
                if (!silent) Console.WriteLine("Removed " + binDir + " from User PATH.");
            }

            if (!silent)
            {
                Console.ForegroundColor = ConsoleColor.Green;
                Console.WriteLine("\n[SUCCESS] CAT CLI has been uninstalled successfully.\n");
                Console.ResetColor();
            }
            return 0;
        }

        static void WriteShim(string binDir, string filename, string pyExe, string module)
        {
            string path = Path.Combine(binDir, filename);
            StringBuilder sb = new StringBuilder();
            sb.AppendLine("@echo off");
            sb.AppendLine("setlocal enabledelayedexpansion");
            sb.AppendLine("set \"CAT_INSTALL_DIR=%~dp0..\"");
            sb.AppendLine("if exist \"%CAT_INSTALL_DIR%\\lib\\calc_terminal\" (");
            sb.AppendLine("    set \"PYTHONPATH=%CAT_INSTALL_DIR%\\lib;!PYTHONPATH!\"");
            sb.AppendLine(")");
            sb.AppendLine("\"" + pyExe + "\" -m " + module + " %*");
            File.WriteAllText(path, sb.ToString(), Encoding.ASCII);
        }

        static void WritePs1Shim(string binDir, string filename, string pyExe)
        {
            string path = Path.Combine(binDir, filename);
            StringBuilder sb = new StringBuilder();
            sb.AppendLine("$ErrorActionPreference = \"Stop\"");
            sb.AppendLine("$installDir = Split-Path -Parent $PSScriptRoot");
            sb.AppendLine("if (Test-Path (Join-Path $installDir \"lib\\calc_terminal\")) {");
            sb.AppendLine("    $env:PYTHONPATH = (Join-Path $installDir \"lib\") + \";\" + $env:PYTHONPATH");
            sb.AppendLine("}");
            sb.AppendLine("& \"" + pyExe + "\" -m calc_terminal.cli @args");
            File.WriteAllText(path, sb.ToString(), Encoding.ASCII);
        }

        static void CopyDirectory(string sourceDir, string destinationDir)
        {
            Directory.CreateDirectory(destinationDir);
            foreach (string file in Directory.GetFiles(sourceDir))
            {
                string ext = Path.GetExtension(file).ToLowerInvariant();
                if (ext == ".sqlite-shm" || ext == ".sqlite-wal" || ext == ".pyc")
                    continue;
                try
                {
                    string destFile = Path.Combine(destinationDir, Path.GetFileName(file));
                    File.Copy(file, destFile, true);
                }
                catch { }
            }
            foreach (string subDir in Directory.GetDirectories(sourceDir))
            {
                string dirName = Path.GetFileName(subDir);
                if (dirName == "__pycache__" || dirName == ".pytest_cache" || dirName == "tests")
                    continue;
                string destSubDir = Path.Combine(destinationDir, dirName);
                CopyDirectory(subDir, destSubDir);
            }
        }
    }
}
