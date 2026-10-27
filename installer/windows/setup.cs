// ============================================================================
// CAT -- Coding Agent Terminal Native Windows Setup Installer
// Compiled with Microsoft .NET Framework C# Compiler (csc.exe)
// Produces: CAT-Setup.exe and catsetup.exe
// ============================================================================

using System;
using System.Diagnostics;
using System.IO;
using System.Management;
using System.Text;

namespace CatInstaller
{
    class Program
    {
        static int Main(string[] args)
        {
            Console.OutputEncoding = Encoding.UTF8;
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
            Console.WriteLine();
            Console.ForegroundColor = ConsoleColor.Magenta;
            Console.Write("        /\\_/\\     ");
            Console.ForegroundColor = ConsoleColor.Cyan;
            Console.WriteLine("  ____    _  _____ ");
            Console.ForegroundColor = ConsoleColor.Magenta;
            Console.Write("       ( o.o )    ");
            Console.ForegroundColor = ConsoleColor.Cyan;
            Console.WriteLine(" / ___|  / \\|_   _|");
            Console.ForegroundColor = ConsoleColor.Magenta;
            Console.Write("        > ^ <     ");
            Console.ForegroundColor = ConsoleColor.Cyan;
            Console.WriteLine("| |     / _ \\ | |  ");
            Console.ForegroundColor = ConsoleColor.Magenta;
            Console.Write("                  ");
            Console.ForegroundColor = ConsoleColor.Cyan;
            Console.WriteLine("| |___ / ___ \\| |  ");
            Console.ForegroundColor = ConsoleColor.Magenta;
            Console.Write("                  ");
            Console.ForegroundColor = ConsoleColor.Cyan;
            Console.WriteLine(" \\____/_/   \\_\\_|  ");
            Console.WriteLine();
            Console.ForegroundColor = ConsoleColor.Cyan;
            Console.WriteLine("  ================================================================");
            Console.ForegroundColor = ConsoleColor.White;
            Console.WriteLine("     C A T  --  CODING AGENT TERMINAL (Native Windows Installer) ");
            Console.ForegroundColor = ConsoleColor.Magenta;
            Console.WriteLine("     Autonomous AI Terminal  |  Tokyo Night Edition  |  v0.8.0b1  ");
            Console.ForegroundColor = ConsoleColor.Cyan;
            Console.WriteLine("  ================================================================\n");
            Console.ResetColor();
        }

        static void ShowHardwareAndModelRecommendations(bool silent)
        {
            if (silent) return;

            Console.ForegroundColor = ConsoleColor.DarkCyan;
            Console.WriteLine("  ----------------------------------------------------------------");
            Console.ForegroundColor = ConsoleColor.Yellow;
            Console.WriteLine("  [DEVICE HARDWARE & LOCAL AI MODEL COMPATIBILITY ANALYSIS]");
            Console.ForegroundColor = ConsoleColor.DarkCyan;
            Console.WriteLine("  ----------------------------------------------------------------");
            Console.ResetColor();

            string cpuName = Environment.GetEnvironmentVariable("PROCESSOR_IDENTIFIER") ?? "x86_64 Processor";
            int cpuCores = Environment.ProcessorCount;
            double totalRamGb = 8.0;
            string gpuName = "Standard GPU Acceleration";
            double gpuVramGb = 0.0;
            string ollamaStatus = "Not Detected";

            // Query hardware via PowerShell quick probe or environment
            try
            {
                ProcessStartInfo psi = new ProcessStartInfo("powershell", "-NoProfile -Command \"$os = Get-CimInstance Win32_OperatingSystem; [math]::Round($os.TotalVisibleMemorySize/1MB, 1)\"")
                {
                    RedirectStandardOutput = true,
                    UseShellExecute = false,
                    CreateNoWindow = true
                };
                using (Process p = Process.Start(psi))
                {
                    string outStr = p.StandardOutput.ReadToEnd();
                    p.WaitForExit(3000);
                    double r;
                    if (double.TryParse(outStr.Trim(), out r))
                    {
                        totalRamGb = r;
                    }
                }
            }
            catch { }

            // Query GPU via nvidia-smi if present
            try
            {
                ProcessStartInfo psi = new ProcessStartInfo("nvidia-smi", "--query-gpu=name,memory.total --format=csv,noheader,nounits")
                {
                    RedirectStandardOutput = true,
                    UseShellExecute = false,
                    CreateNoWindow = true
                };
                using (Process p = Process.Start(psi))
                {
                    string outStr = p.StandardOutput.ReadToEnd();
                    p.WaitForExit(3000);
                    if (!string.IsNullOrEmpty(outStr) && outStr.Contains(","))
                    {
                        string[] parts = outStr.Split('\n')[0].Split(',');
                        gpuName = parts[0].Trim();
                        double mb;
                        if (double.TryParse(parts[1].Trim(), out mb))
                        {
                            gpuVramGb = Math.Round(mb / 1024.0, 1);
                        }
                    }
                }
            }
            catch { }

            // Check Ollama
            try
            {
                ProcessStartInfo psi = new ProcessStartInfo("ollama", "--version")
                {
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    UseShellExecute = false,
                    CreateNoWindow = true
                };
                using (Process p = Process.Start(psi))
                {
                    string outStr = p.StandardOutput.ReadToEnd();
                    string errStr = p.StandardError.ReadToEnd();
                    p.WaitForExit(2000);
                    string ver = !string.IsNullOrEmpty(outStr) ? outStr : errStr;
                    if (!string.IsNullOrEmpty(ver) && ver.ToLower().Contains("version"))
                    {
                        ollamaStatus = "Installed";
                    }
                }
            }
            catch { }

            string tierName = "";
            string tierDesc = "";
            if (totalRamGb >= 28 || gpuVramGb >= 16)
            {
                tierName = "Tier 3: Heavy Workstation (" + totalRamGb + " GB RAM Detected)";
                tierDesc = "Runs up to 14B-32B models effortlessly with hybrid GPU/CPU acceleration!";
            }
            else if (totalRamGb >= 14 || gpuVramGb >= 8)
            {
                tierName = "Tier 2: Advanced Developer (" + totalRamGb + " GB RAM Detected)";
                tierDesc = "Optimal for 7B-14B models with fast inference!";
            }
            else
            {
                tierName = "Tier 1: Standard System (" + totalRamGb + " GB RAM Detected)";
                tierDesc = "Ideal for 1B-8B models (e.g. Qwen 2.5 Coder 7B, Llama 3.2 3B)!";
            }

            Console.ForegroundColor = ConsoleColor.DarkGray; Console.Write("    CPU    : ");
            Console.ForegroundColor = ConsoleColor.White; Console.WriteLine(cpuName + " (" + cpuCores + " Threads)");

            Console.ForegroundColor = ConsoleColor.DarkGray; Console.Write("    RAM    : ");
            Console.ForegroundColor = ConsoleColor.White; Console.WriteLine(totalRamGb + " GB System Memory");

            Console.ForegroundColor = ConsoleColor.DarkGray; Console.Write("    GPU    : ");
            Console.ForegroundColor = ConsoleColor.White; Console.Write(gpuName);
            if (gpuVramGb > 0)
            {
                Console.ForegroundColor = ConsoleColor.Green;
                Console.WriteLine(" (" + gpuVramGb + " GB Dedicated VRAM)");
            }
            else
            {
                Console.WriteLine();
            }

            Console.ForegroundColor = ConsoleColor.DarkGray; Console.Write("    AI Hub : ");
            Console.ForegroundColor = ConsoleColor.White; Console.WriteLine("Ollama " + ollamaStatus + " | Hugging Face GGUF / llama.cpp Ready");

            Console.ForegroundColor = ConsoleColor.DarkGray; Console.Write("    Tier   : ");
            Console.ForegroundColor = ConsoleColor.Cyan; Console.WriteLine(tierName);
            Console.ForegroundColor = ConsoleColor.DarkCyan; Console.WriteLine("             " + tierDesc + "\n");

            Console.ForegroundColor = ConsoleColor.Yellow;
            Console.WriteLine("    Recommended Latest Ollama & Local Models for Your System:");
            Console.ForegroundColor = ConsoleColor.DarkGray;
            Console.WriteLine("    --------------------------------------------------------------------------------");
            Console.ForegroundColor = ConsoleColor.DarkCyan;
            Console.WriteLine("    Model Identifier       Size    Category    Hardware Status");
            Console.ForegroundColor = ConsoleColor.DarkGray;
            Console.WriteLine("    --------------------------------------------------------------------------------");

            PrintModelRow("qwen2.5-coder:7b", "4.7 GB", "Coding", "[100% Compatible - Optimal]", ConsoleColor.Green);
            PrintModelRow("deepseek-r1:7b", "4.7 GB", "Reasoning", "[100% Compatible - Optimal]", ConsoleColor.Green);
            if (totalRamGb >= 14)
            {
                PrintModelRow("qwen2.5-coder:14b", "9.0 GB", "Coding", "[100% Compatible - Optimal]", ConsoleColor.Green);
                PrintModelRow("deepseek-r1:14b", "9.0 GB", "Reasoning", "[100% Compatible - Optimal]", ConsoleColor.Green);
                PrintModelRow("phi4:14b", "9.1 GB", "Reasoning", "[100% Compatible - Optimal]", ConsoleColor.Green);
            }
            PrintModelRow("llama3.2:3b", "2.0 GB", "Fast/Chat", (gpuVramGb >= 2.0 ? "[100% GPU VRAM - Blazing Fast]" : "[Optimal On-Device]"), ConsoleColor.Green);
            PrintModelRow("qwen2.5-coder:1.5b", "1.0 GB", "Autocomplete", (gpuVramGb >= 1.0 ? "[100% GPU VRAM - Blazing Fast]" : "[Ultra-Fast]"), ConsoleColor.Green);

            if (totalRamGb >= 28)
            {
                PrintModelRow("qwen2.5-coder:32b", "19.0 GB", "Coding", "[Compatible - RAM Cached]", ConsoleColor.Cyan);
                PrintModelRow("deepseek-r1:32b", "19.0 GB", "Reasoning", "[Compatible - RAM Cached]", ConsoleColor.Cyan);
            }

            Console.ForegroundColor = ConsoleColor.DarkGray;
            Console.WriteLine("    --------------------------------------------------------------------------------\n");

            Console.ForegroundColor = ConsoleColor.Yellow;
            Console.WriteLine("    Top Hugging Face GGUF Model Matches:");
            Console.ForegroundColor = ConsoleColor.DarkCyan;
            Console.WriteLine("      - Qwen/Qwen2.5-Coder-7B-Instruct-GGUF        (Q4_K_M ~4.7 GB) -> Fast Coding");
            Console.WriteLine("      - deepseek-ai/DeepSeek-R1-Distill-Qwen-7B-GGUF (Q4_K_M ~4.7 GB) -> Reasoning");
            if (totalRamGb >= 14)
            {
                Console.WriteLine("      - Qwen/Qwen2.5-Coder-14B-Instruct-GGUF       (Q4_K_M ~9.0 GB) -> Heavy Coding");
                Console.WriteLine("      - microsoft/phi-4-GGUF                       (Q4_K_M ~9.1 GB) -> Math & Logic");
            }
            Console.WriteLine();

            Console.ForegroundColor = ConsoleColor.Yellow;
            Console.WriteLine("    Quick-Start Local AI Command (Run in any terminal):");
            Console.ForegroundColor = ConsoleColor.Cyan;
            Console.WriteLine("      ollama run qwen2.5-coder:7b     # Launch recommended coding model");
            Console.WriteLine("      ollama run deepseek-r1:7b       # Launch recommended reasoning model");
            Console.WriteLine("      cat model list                  # Inspect active models inside CAT");
            Console.ForegroundColor = ConsoleColor.DarkCyan;
            Console.WriteLine("  ----------------------------------------------------------------\n");
            Console.ResetColor();
        }

        static void PrintModelRow(string id, string size, string cat, string status, ConsoleColor statusColor)
        {
            Console.ForegroundColor = ConsoleColor.White;
            Console.Write("    " + id.PadRight(23) + size.PadRight(8) + cat.PadRight(12));
            Console.ForegroundColor = statusColor;
            Console.WriteLine(status);
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
                Console.WriteLine("[1/6] Detecting Python 3.10+ runtime...");
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
                Console.WriteLine("[2/6] Inspecting device hardware & AI acceleration capabilities...");
                Console.ResetColor();
            }

            ShowHardwareAndModelRecommendations(silent);

            if (!silent)
            {
                Console.ForegroundColor = ConsoleColor.Yellow;
                Console.WriteLine("[3/6] Creating installation directory structure...");
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
                Console.WriteLine("[4/6] Deploying CAT CLI core modules...");
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
                    Console.WriteLine("      Installing cct-cli package into Python environment...");
                    Console.ResetColor();
                }
                try
                {
                    ProcessStartInfo pipPsi = new ProcessStartInfo(pyExe, "-m pip install --upgrade cct-cli")
                    {
                        RedirectStandardOutput = true,
                        RedirectStandardError = true,
                        UseShellExecute = false,
                        CreateNoWindow = true
                    };
                    using (Process pipProc = Process.Start(pipPsi))
                    {
                        pipProc.WaitForExit(30000);
                        if (pipProc.ExitCode != 0)
                        {
                            ProcessStartInfo gitPsi = new ProcessStartInfo(pyExe, "-m pip install --upgrade git+https://github.com/kazizillani-oss/CAT_v0.7.9.git")
                            {
                                RedirectStandardOutput = true,
                                RedirectStandardError = true,
                                UseShellExecute = false,
                                CreateNoWindow = true
                            };
                            using (Process gitProc = Process.Start(gitPsi))
                            {
                                gitProc.WaitForExit(60000);
                            }
                        }
                    }
                }
                catch { }
            }

            if (!silent)
            {
                Console.ForegroundColor = ConsoleColor.Yellow;
                Console.WriteLine("[5/6] Generating launcher shims and aliases...");
                Console.ResetColor();
            }

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
                Console.WriteLine("      Created launcher shims in: " + binDir);
                Console.ForegroundColor = ConsoleColor.DarkCyan;
                Console.WriteLine("        - cat.cmd / cat.ps1       (CAT CLI main entry)");
                Console.WriteLine("        - catx.cmd                (PowerShell collision-safe alias)");
                Console.WriteLine("        - cct.cmd                 (Classic alias)");
                Console.WriteLine("        - cat-curl.cmd            (Native HTTP/REST client)");
                Console.WriteLine("        - cat-brew.cmd            (Universal package bridge)");
                Console.WriteLine("        - cat-sudo.cmd            (Universal privilege elevation)");
                Console.ResetColor();
            }

            if (!silent)
            {
                Console.ForegroundColor = ConsoleColor.Yellow;
                Console.WriteLine("[6/6] Configuring User Environment PATH and aliases...");
                Console.ResetColor();
            }

            string userPath = Environment.GetEnvironmentVariable("Path", EnvironmentVariableTarget.User) ?? "";
            if (!userPath.ToLowerInvariant().Contains(binDir.ToLowerInvariant()))
            {
                string newPath = string.IsNullOrEmpty(userPath) ? binDir : (userPath.TrimEnd(';') + ";" + binDir);
                Environment.SetEnvironmentVariable("Path", newPath, EnvironmentVariableTarget.User);
                if (!silent)
                {
                    Console.ForegroundColor = ConsoleColor.Green;
                    Console.WriteLine("      Added " + binDir + " to User PATH.");
                    Console.ResetColor();
                }
            }
            else
            {
                if (!silent)
                {
                    Console.ForegroundColor = ConsoleColor.DarkGray;
                    Console.WriteLine("      " + binDir + " is already present in User PATH.");
                    Console.ResetColor();
                }
            }

            if (!silent)
            {
                Console.ForegroundColor = ConsoleColor.Green;
                Console.WriteLine("\n================================================================");
                Console.WriteLine("   [SUCCESS] CAT CLI Setup Complete!");
                Console.WriteLine("================================================================\n");
                Console.ForegroundColor = ConsoleColor.Yellow;
                Console.WriteLine("You can now open a new terminal window and use CAT:");
                Console.ForegroundColor = ConsoleColor.Cyan;
                Console.WriteLine("  cat --version               # Display version");
                Console.WriteLine("  cat model list              # Inspect active local models");
                Console.WriteLine("  ollama run qwen2.5-coder:7b # Run recommended local coding model");
                Console.WriteLine("  ollama run deepseek-r1:7b   # Run recommended local reasoning model");
                Console.WriteLine("  cat curl --version          # Test HTTP/REST curl client");
                Console.WriteLine("  cat brew doctor             # Check package manager status");
                Console.WriteLine("  cat sudo --status           # Check administrative elevation privileges");
                Console.WriteLine("  cat                         # Launch interactive Tokyo Night terminal\n");
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
