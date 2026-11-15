// Datasmith DirectLink C# Background Worker for IngeTrazo
// Strict C# 5.0 compatibility for .NET 4.0 / 4.5 csc.exe

using System;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

namespace IngeTrazoTwinmotionWorker
{
    [StructLayout(LayoutKind.Sequential, Pack = 1)]
    public struct FInitOptions
    {
        [MarshalAs(UnmanagedType.I1)]
        public bool bLogNone;         // offset 0: -logcmds="Global None"

        [MarshalAs(UnmanagedType.I1)]
        public bool bSaveToUserDir;   // offset 1: -SaveToUserDir

        [MarshalAs(UnmanagedType.I1)]
        public bool bEnableMessaging; // offset 2: -Messaging (enables Unreal UDP MessageBus for DirectLink)

        [MarshalAs(UnmanagedType.I1)]
        public bool bEnableUI;        // offset 3: requires RemoteEngineDir if true

        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 60)]
        public byte[] padding;
    }

    class Program
    {
        private const string DatasmithDll = "DatasmithFacadeCSharp.dll";
        private const string DefaultRuntimeDir = @"C:\ProgramData\McNeel\Rhinoceros\7.0\Plug-ins\Datasmith Rhino Exporter (d1fdc795-b334-4933-b680-088119cdc6bb)";

        [DllImport("kernel32.dll", CharSet = CharSet.Auto, SetLastError = true)]
        private static extern bool SetDllDirectory(string lpPathName);

        // FDatasmithExporterManager
        [DllImport(DatasmithDll, EntryPoint = "?Initialize@FDatasmithExporterManager@@SA_NAEBUFInitOptions@1@@Z", CallingConvention = CallingConvention.Cdecl)]
        private static extern bool InitializeManagerWithOptions(ref FInitOptions options);

        [DllImport(DatasmithDll, EntryPoint = "?Initialize@FDatasmithExporterManager@@SA_NXZ", CallingConvention = CallingConvention.Cdecl)]
        private static extern bool InitializeManagerDefault();

        [DllImport(DatasmithDll, EntryPoint = "?WasInitializedWithMessaging@FDatasmithExporterManager@@SA_NXZ", CallingConvention = CallingConvention.Cdecl)]
        private static extern bool WasInitializedWithMessaging();

        // FDatasmithFacadeDirectLink
        [DllImport(DatasmithDll, EntryPoint = "?Init@FDatasmithFacadeDirectLink@@SA_N_NPEB_W@Z", CallingConvention = CallingConvention.Cdecl)]
        private static extern bool InitDirectLink(bool bVerbose, [MarshalAs(UnmanagedType.LPWStr)] string cacheDir);

        [DllImport(DatasmithDll, EntryPoint = "CSharp_new_FDatasmithFacadeDirectLink", CallingConvention = CallingConvention.Cdecl)]
        private static extern IntPtr NewDirectLink();

        [DllImport(DatasmithDll, EntryPoint = "CSharp_delete_FDatasmithFacadeDirectLink", CallingConvention = CallingConvention.Cdecl)]
        private static extern void DeleteDirectLink(IntPtr directLink);

        [DllImport(DatasmithDll, EntryPoint = "CSharp_FDatasmithFacadeDirectLink_InitializeForScene", CallingConvention = CallingConvention.Cdecl)]
        private static extern bool InitializeForScene(IntPtr directLink, IntPtr scene);

        [DllImport(DatasmithDll, EntryPoint = "CSharp_FDatasmithFacadeDirectLink_UpdateScene", CallingConvention = CallingConvention.Cdecl)]
        private static extern bool UpdateScene(IntPtr directLink, IntPtr scene);

        [DllImport(DatasmithDll, EntryPoint = "CSharp_FDatasmithFacadeDirectLink_CloseCurrentSource", CallingConvention = CallingConvention.Cdecl)]
        private static extern void CloseCurrentSource(IntPtr directLink);

        [DllImport(DatasmithDll, EntryPoint = "CSharp_FDatasmithFacadeDirectLink_ValidateCommunicationSetup", CallingConvention = CallingConvention.Cdecl)]
        private static extern bool ValidateCommunicationSetup();

        // FDatasmithFacadeScene
        [DllImport(DatasmithDll, EntryPoint = "CSharp_new_FDatasmithFacadeScene", CallingConvention = CallingConvention.Cdecl)]
        private static extern IntPtr NewScene(
            [MarshalAs(UnmanagedType.LPWStr)] string inProjectName,
            [MarshalAs(UnmanagedType.LPWStr)] string inHostName,
            [MarshalAs(UnmanagedType.LPWStr)] string inProductVersion,
            [MarshalAs(UnmanagedType.LPWStr)] string inExporterVersion);

        [DllImport(DatasmithDll, EntryPoint = "CSharp_delete_FDatasmithFacadeScene", CallingConvention = CallingConvention.Cdecl)]
        private static extern void DeleteScene(IntPtr scene);

        [DllImport(DatasmithDll, EntryPoint = "CSharp_FDatasmithFacadeScene_SetName", CallingConvention = CallingConvention.Cdecl)]
        private static extern void SetSceneName(IntPtr scene, [MarshalAs(UnmanagedType.LPWStr)] string name);

        [DllImport(DatasmithDll, EntryPoint = "CSharp_FDatasmithFacadeScene_SetOutputPath", CallingConvention = CallingConvention.Cdecl)]
        private static extern void SetOutputPath(IntPtr scene, [MarshalAs(UnmanagedType.LPWStr)] string outputPath);

        [DllImport(DatasmithDll, EntryPoint = "CSharp_FDatasmithFacadeScene_AddMesh", CallingConvention = CallingConvention.Cdecl)]
        private static extern void AddMesh(IntPtr scene, IntPtr meshElement);

        [DllImport(DatasmithDll, EntryPoint = "CSharp_FDatasmithFacadeScene_AddActor", CallingConvention = CallingConvention.Cdecl)]
        private static extern void AddActor(IntPtr scene, IntPtr actor);

        [DllImport(DatasmithDll, EntryPoint = "CSharp_FDatasmithFacadeScene_PreExport", CallingConvention = CallingConvention.Cdecl)]
        private static extern void PreExport(IntPtr scene);

        [DllImport(DatasmithDll, EntryPoint = "CSharp_FDatasmithFacadeScene_ExportScene__SWIG_0", CallingConvention = CallingConvention.Cdecl)]
        private static extern bool ExportScene(IntPtr scene, [MarshalAs(UnmanagedType.LPWStr)] string inOutputPath, bool bCleanUp);

        [DllImport(DatasmithDll, EntryPoint = "CSharp_FDatasmithFacadeScene_Reset", CallingConvention = CallingConvention.Cdecl)]
        private static extern void ResetScene(IntPtr scene);

        [DllImport(DatasmithDll, EntryPoint = "CSharp_FDatasmithFacadeScene_ExportDatasmithMesh__SWIG_1", CallingConvention = CallingConvention.Cdecl)]
        private static extern IntPtr ExportDatasmithMesh(IntPtr scene, IntPtr mesh);

        // FDatasmithFacadeMesh
        [DllImport(DatasmithDll, EntryPoint = "CSharp_new_FDatasmithFacadeMesh", CallingConvention = CallingConvention.Cdecl)]
        private static extern IntPtr NewMesh();

        [DllImport(DatasmithDll, EntryPoint = "CSharp_FDatasmithFacadeMesh_SetName", CallingConvention = CallingConvention.Cdecl)]
        private static extern void SetMeshName(IntPtr mesh, [MarshalAs(UnmanagedType.LPWStr)] string name);

        [DllImport(DatasmithDll, EntryPoint = "CSharp_FDatasmithFacadeMesh_SetVerticesCount", CallingConvention = CallingConvention.Cdecl)]
        private static extern void SetVerticesCount(IntPtr mesh, int count);

        [DllImport(DatasmithDll, EntryPoint = "CSharp_FDatasmithFacadeMesh_SetVertex", CallingConvention = CallingConvention.Cdecl)]
        private static extern void SetVertex(IntPtr mesh, int index, float x, float y, float z);

        [DllImport(DatasmithDll, EntryPoint = "CSharp_FDatasmithFacadeMesh_SetFacesCount", CallingConvention = CallingConvention.Cdecl)]
        private static extern void SetFacesCount(IntPtr mesh, int count);

        [DllImport(DatasmithDll, EntryPoint = "CSharp_FDatasmithFacadeMesh_SetFace__SWIG_1", CallingConvention = CallingConvention.Cdecl)]
        private static extern void SetFace(IntPtr mesh, int index, int v0, int v1, int v2);

        // FDatasmithFacadeActorMesh
        [DllImport(DatasmithDll, EntryPoint = "CSharp_new_FDatasmithFacadeActorMesh", CallingConvention = CallingConvention.Cdecl)]
        private static extern IntPtr NewActorMesh([MarshalAs(UnmanagedType.LPWStr)] string name);

        [DllImport(DatasmithDll, EntryPoint = "CSharp_FDatasmithFacadeActorMesh_SetMesh", CallingConvention = CallingConvention.Cdecl)]
        private static extern void SetActorMesh(IntPtr actor, [MarshalAs(UnmanagedType.LPWStr)] string meshName);

        private static TcpListener _listener;
        private static bool _isRunning = true;
        private static int _port = 19850;

        private static IntPtr _directLinkPtr = IntPtr.Zero;
        private static IntPtr _scenePtr = IntPtr.Zero;
        private static bool _datasmithReady = false;
        private static string _sourceName = "IngeTrazo LiveSync";
        private static string _cacheDir = null;

        static void Main(string[] args)
        {
            Console.WriteLine("[DatasmithWorker] Starting IngeTrazo Twinmotion DirectLink Worker...");

            int customPort;
            if (args.Length > 0 && int.TryParse(args[0], out customPort))
            {
                _port = customPort;
            }

            if (args.Length > 1 && !string.IsNullOrEmpty(args[1]))
            {
                _sourceName = args[1];
            }

            // 1. Configure DLL search directory for native Datasmith runtime
            string runtimeDir = DefaultRuntimeDir;
            if (Directory.Exists(runtimeDir))
            {
                SetDllDirectory(runtimeDir);
                Console.WriteLine(string.Format("[DatasmithWorker] Native runtime path set: {0}", runtimeDir));
            }

            // 2. Initialize Datasmith Exporter Engine with Messaging enabled
            try
            {
                InitDatasmith(_sourceName);
            }
            catch (Exception ex)
            {
                Console.WriteLine(string.Format("[DatasmithWorker] Warning during Datasmith initialization: {0}", ex.Message));
            }

            // 3. Start local TCP server for IngeTrazo IPC
            try
            {
                _listener = new TcpListener(IPAddress.Loopback, _port);
                _listener.Start();
                Console.WriteLine(string.Format("[DatasmithWorker] IPC server listening on 127.0.0.1:{0}", _port));

                while (_isRunning)
                {
                    if (_listener.Pending())
                    {
                        TcpClient client = _listener.AcceptTcpClient();
                        Thread clientThread = new Thread(() => HandleClient(client));
                        clientThread.IsBackground = true;
                        clientThread.Start();
                    }
                    Thread.Sleep(50);
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine(string.Format("[DatasmithWorker] Fatal socket error: {0}", ex.Message));
            }
            finally
            {
                ShutdownDatasmith();
                if (_listener != null)
                {
                    _listener.Stop();
                }
            }
        }

        private static void InitDatasmith(string sourceName)
        {
            // A. Initialize Exporter Manager with messaging enabled
            FInitOptions options = new FInitOptions();
            options.bLogNone = false;
            options.bSaveToUserDir = false;
            options.bEnableMessaging = true;
            options.bEnableUI = false;
            options.padding = new byte[60];

            bool mgrOk = false;
            try
            {
                mgrOk = InitializeManagerWithOptions(ref options);
                Console.WriteLine(string.Format("[DatasmithWorker] FDatasmithExporterManager::Initialize(options) -> {0}", mgrOk));
            }
            catch
            {
                mgrOk = InitializeManagerDefault();
                Console.WriteLine(string.Format("[DatasmithWorker] FDatasmithExporterManager::Initialize() fallback -> {0}", mgrOk));
            }

            bool msgActive = WasInitializedWithMessaging();
            Console.WriteLine(string.Format("[DatasmithWorker] WasInitializedWithMessaging -> {0}", msgActive));

            // B. Initialize DirectLink with local cache directory
            _cacheDir = Path.Combine(Path.GetTempPath(), "IngeTrazo_DirectLink");
            if (!Directory.Exists(_cacheDir))
            {
                Directory.CreateDirectory(_cacheDir);
            }

            bool dlOk = InitDirectLink(true, _cacheDir);
            Console.WriteLine(string.Format("[DatasmithWorker] FDatasmithFacadeDirectLink::Init -> {0}", dlOk));

            // C. Create Scene and DirectLink objects
            _scenePtr = NewScene(_sourceName, "IngeTrazo", "1.0", "1.0");
            SetSceneName(_scenePtr, _sourceName);
            SetOutputPath(_scenePtr, _cacheDir);
            Console.WriteLine(string.Format("[DatasmithWorker] Scene created: 0x{0:X} (output: {1})", _scenePtr.ToInt64(), _cacheDir));

            _directLinkPtr = NewDirectLink();
            Console.WriteLine(string.Format("[DatasmithWorker] DirectLink created: 0x{0:X}", _directLinkPtr.ToInt64()));

            // D. Initialize DirectLink for the Scene
            if (_directLinkPtr != IntPtr.Zero && _scenePtr != IntPtr.Zero)
            {
                bool sceneBound = InitializeForScene(_directLinkPtr, _scenePtr);
                Console.WriteLine(string.Format("[DatasmithWorker] InitializeForScene -> {0}", sceneBound));

                // E. Broadcast initial snapshot to announce endpoint to Twinmotion
                bool snapshotPushed = UpdateScene(_directLinkPtr, _scenePtr);
                Console.WriteLine(string.Format("[DatasmithWorker] Initial UpdateScene -> {0}", snapshotPushed));

                _datasmithReady = sceneBound && snapshotPushed;
            }

            Console.WriteLine(string.Format("[DatasmithWorker] DirectLink status: {0} (Broadcasting source: '{1}')", 
                _datasmithReady ? "ONLINE" : "PENDING", sourceName));
        }

        private static void ShutdownDatasmith()
        {
            if (_directLinkPtr != IntPtr.Zero)
            {
                try { CloseCurrentSource(_directLinkPtr); } catch { }
                try { DeleteDirectLink(_directLinkPtr); } catch { }
                _directLinkPtr = IntPtr.Zero;
            }
            if (_scenePtr != IntPtr.Zero)
            {
                try { DeleteScene(_scenePtr); } catch { }
                _scenePtr = IntPtr.Zero;
            }
            _datasmithReady = false;
            Console.WriteLine("[DatasmithWorker] DirectLink handles released.");
        }

        private static void HandleClient(TcpClient client)
        {
            Console.WriteLine("[DatasmithWorker] IngeTrazo Python extension connected.");
            using (NetworkStream stream = client.GetStream())
            using (StreamReader reader = new StreamReader(stream, new UTF8Encoding(false)))
            using (StreamWriter writer = new StreamWriter(stream, new UTF8Encoding(false)) { AutoFlush = true })
            {
                while (client.Connected)
                {
                    string line = reader.ReadLine();
                    if (string.IsNullOrEmpty(line)) break;

                    string response = ProcessCommand(line);
                    writer.WriteLine(response);
                }
            }
            Console.WriteLine("[DatasmithWorker] Client disconnected.");
        }

        private static string ProcessCommand(string commandJson)
        {
            if (commandJson.Contains("\"cmd\":\"PING\""))
            {
                return string.Format("{{\"status\":\"OK\",\"message\":\"PONG\",\"datasmithReady\":{0}}}", _datasmithReady ? "true" : "false");
            }

            if (commandJson.Contains("\"cmd\":\"CAMERA\""))
            {
                return "{\"status\":\"OK\",\"message\":\"Camera updated\"}";
            }

            if (commandJson.Contains("\"cmd\":\"SYNC\""))
            {
                bool synced = false;
                if (_directLinkPtr != IntPtr.Zero && _scenePtr != IntPtr.Zero)
                {
                    try
                    {
                        string binFile = null;
                        int fileIdx = commandJson.IndexOf("\"file\":");
                        if (fileIdx > 0)
                        {
                            int start = commandJson.IndexOf('"', fileIdx + 7);
                            if (start > 0)
                            {
                                int end = commandJson.IndexOf('"', start + 1);
                                if (end > start)
                                {
                                    binFile = commandJson.Substring(start + 1, end - start - 1);
                                }
                            }
                        }

                        if (string.IsNullOrEmpty(binFile) || !File.Exists(binFile))
                        {
                            string defaultBin = Path.Combine(Path.GetTempPath(), "IngeTrazo_DirectLink", "scene_geometry.bin");
                            if (File.Exists(defaultBin)) binFile = defaultBin;
                        }

                        if (!string.IsNullOrEmpty(binFile) && File.Exists(binFile))
                        {
                            Console.WriteLine(string.Format("[DatasmithWorker] Importing geometry from: {0}", binFile));
                            try {
                                ResetScene(_scenePtr);
                                SetSceneName(_scenePtr, _sourceName);
                                SetOutputPath(_scenePtr, _cacheDir);
                            } catch { }

                            using (BinaryReader br = new BinaryReader(File.OpenRead(binFile)))
                            {
                                int numMeshes = br.ReadInt32();
                                for (int m = 0; m < numMeshes; m++)
                                {
                                    short nameLen = br.ReadInt16();
                                    byte[] nameBytes = br.ReadBytes(nameLen);
                                    string meshName = Encoding.UTF8.GetString(nameBytes);

                                    int numVerts = br.ReadInt32();
                                    IntPtr meshPtr = NewMesh();
                                    SetMeshName(meshPtr, meshName);
                                    SetVerticesCount(meshPtr, numVerts);

                                    for (int v = 0; v < numVerts; v++)
                                    {
                                        float x = br.ReadSingle();
                                        float y = br.ReadSingle();
                                        float z = br.ReadSingle();
                                        SetVertex(meshPtr, v, x, y, z);
                                    }

                                    int numTris = br.ReadInt32();
                                    SetFacesCount(meshPtr, numTris);
                                    for (int t = 0; t < numTris; t++)
                                    {
                                        int v0 = br.ReadInt32();
                                        int v1 = br.ReadInt32();
                                        int v2 = br.ReadInt32();
                                        SetFace(meshPtr, t, v0, v1, v2);
                                    }

                                    IntPtr meshElemPtr = ExportDatasmithMesh(_scenePtr, meshPtr);
                                    if (meshElemPtr != IntPtr.Zero)
                                    {
                                        AddMesh(_scenePtr, meshElemPtr);

                                        IntPtr actorPtr = NewActorMesh(meshName + "_Actor");
                                        SetActorMesh(actorPtr, meshName);
                                        AddActor(_scenePtr, actorPtr);
                                    }
                                }
                                Console.WriteLine(string.Format("[DatasmithWorker] Processed {0} mesh(es).", numMeshes));
                            }

                            PreExport(_scenePtr);
                            string udatasmithFile = Path.Combine(_cacheDir, _sourceName + ".udatasmith");
                            ExportScene(_scenePtr, udatasmithFile, false);
                            Console.WriteLine(string.Format("[DatasmithWorker] Scene PreExport and ExportScene to {0} completed.", udatasmithFile));
                        }

                        synced = UpdateScene(_directLinkPtr, _scenePtr);
                        Console.WriteLine(string.Format("[DatasmithWorker] UpdateScene -> {0}", synced));
                    }
                    catch (Exception ex)
                    {
                        Console.WriteLine(string.Format("[DatasmithWorker] SYNC error: {0}", ex.Message));
                        return string.Format("{{\"status\":\"ERROR\",\"message\":\"{0}\"}}", ex.Message.Replace("\"", "'"));
                    }
                }
                return string.Format("{{\"status\":\"OK\",\"message\":\"Snapshot pushed with geometry\",\"synced\":{0}}}", synced ? "true" : "false");
            }

            if (commandJson.Contains("\"cmd\":\"STOP\""))
            {
                _isRunning = false;
                return "{\"status\":\"OK\",\"message\":\"Worker stopping\"}";
            }

            return "{\"status\":\"OK\"}";
        }
    }
}
