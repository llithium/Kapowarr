import AppKit
import Darwin
import Network
import SQLite3

struct LauncherError: LocalizedError {
    let message: String
    var errorDescription: String? { message }
}

final class ServerController {
    let data: URL
    let logs: URL
    private(set) var process: Process?
    private var lock: Int32 = -1
    private var output: FileHandle?
    var onExit: ((Int32) -> Void)?

    init() {
        let home = FileManager.default.homeDirectoryForCurrentUser
        if let override = ProcessInfo.processInfo.environment["KAPOWARR_DATA_DIR"] {
            data = URL(fileURLWithPath: override, isDirectory: true)
            logs = data.appendingPathComponent("logs", isDirectory: true)
        } else {
            data = home.appendingPathComponent("Library/Application Support/Kapowarr", isDirectory: true)
            logs = home.appendingPathComponent("Library/Logs/Kapowarr", isDirectory: true)
        }
    }

    private func savedSettings() throws -> [String: String] {
        let database = data.appendingPathComponent("Kapowarr.db")
        var settings: [String: String] = [:]
        if FileManager.default.fileExists(atPath: database.path) {
            var db: OpaquePointer?
            guard sqlite3_open_v2(database.path, &db, SQLITE_OPEN_READONLY, nil) == SQLITE_OK else {
                if let db { sqlite3_close(db) }
                throw LauncherError(message: "Cannot read the Kapowarr database at \(database.path).")
            }
            defer { sqlite3_close(db) }
            sqlite3_busy_timeout(db, 2000)
            var statement: OpaquePointer?
            let query = "SELECT key, value FROM config WHERE key IN ('port', 'url_base', 'quit_on_browser_close')"
            guard sqlite3_prepare_v2(db, query, -1, &statement, nil) == SQLITE_OK else {
                throw LauncherError(message: "Cannot read Kapowarr's saved settings.")
            }
            defer { sqlite3_finalize(statement) }
            var result = sqlite3_step(statement)
            while result == SQLITE_ROW {
                if let keyText = sqlite3_column_text(statement, 0),
                   let valueText = sqlite3_column_text(statement, 1) {
                    settings[String(cString: keyText)] = String(cString: valueText)
                }
                result = sqlite3_step(statement)
            }
            guard result == SQLITE_DONE else {
                throw LauncherError(message: "Cannot read Kapowarr's saved settings. Try closing its browser tabs again.")
            }
        }
        return settings
    }

    func quitOnBrowserClose() throws -> Bool {
        try savedSettings()["quit_on_browser_close"] != "0"
    }

    func serverURL() throws -> URL {
        let settings = try savedSettings()
        let port = settings["port"] ?? "5656"
        let base = settings["url_base"] ?? ""
        guard let number = Int(port), (1...65535).contains(number),
              let url = URL(string: "http://127.0.0.1:\(number)\(base)/") else {
            throw LauncherError(message: "Kapowarr's saved port or URL base is invalid.")
        }
        return url
    }

    func start(browserSession: BrowserSession? = nil) throws {
        let fm = FileManager.default
        try fm.createDirectory(at: data, withIntermediateDirectories: true)
        try fm.createDirectory(at: logs, withIntermediateDirectories: true)
        lock = Darwin.open(data.appendingPathComponent("launcher.lock").path, O_CREAT | O_RDWR, 0o600)
        guard lock >= 0, flock(lock, LOCK_EX | LOCK_NB) == 0 else {
            throw LauncherError(message: "Kapowarr is already running. Use its menu-bar icon to open it.")
        }
        // Do not pass the lock into the backend or conversion processes.
        _ = fcntl(lock, F_SETFD, FD_CLOEXEC)
        let url = try serverURL()
        let socket = Darwin.socket(AF_INET, SOCK_STREAM, 0)
        guard socket >= 0 else { throw LauncherError(message: "Cannot check Kapowarr's port.") }
        var reuse: Int32 = 1
        setsockopt(socket, SOL_SOCKET, SO_REUSEADDR, &reuse, socklen_t(MemoryLayout<Int32>.size))
        var address = sockaddr_in()
        address.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
        address.sin_family = sa_family_t(AF_INET)
        address.sin_port = in_port_t(url.port!).bigEndian
        address.sin_addr.s_addr = inet_addr("127.0.0.1")
        let available = withUnsafePointer(to: &address) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                Darwin.bind(socket, $0, socklen_t(MemoryLayout<sockaddr_in>.size)) == 0
            }
        }
        Darwin.close(socket)
        guard available else {
            throw LauncherError(message: "Port \(url.port!) is already in use. Quit the other Kapowarr instance or service, then open this app again.")
        }
        guard let resources = Bundle.main.resourceURL else {
            throw LauncherError(message: "Kapowarr's bundled server is missing. Reinstall the app.")
        }
        let server = Process()
        server.executableURL = resources.appendingPathComponent("server/kapowarr-server")
        server.currentDirectoryURL = data
        server.arguments = ["-d", data.path, "-l", logs.path, "-o", "127.0.0.1"]
        if !fm.fileExists(atPath: data.appendingPathComponent("Kapowarr.db").path) {
            let downloads = data.appendingPathComponent("temp_downloads", isDirectory: true)
            try fm.createDirectory(at: downloads, withIntermediateDirectories: true)
            server.arguments! += ["-t", downloads.path]
        }
        var environment = ProcessInfo.processInfo.environment
        environment.removeValue(forKey: "PYTHONHOME")
        environment.removeValue(forKey: "PYTHONPATH")
        environment.removeValue(forKey: "KAPOWARR_RUN_MAIN")
        environment.removeValue(forKey: "KAPOWARR_START_TYPE")
        environment.removeValue(forKey: "KAPOWARR_BROWSER_SESSION_URL")
        environment.removeValue(forKey: "KAPOWARR_BROWSER_SESSION_PROTOCOL")
        if let browserSession {
            environment["KAPOWARR_BROWSER_SESSION_URL"] = browserSession.url?.absoluteString
            environment["KAPOWARR_BROWSER_SESSION_PROTOCOL"] = browserSession.token
        }
        environment["PATH"] = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
        environment["PYTHONUNBUFFERED"] = "1"
        server.environment = environment
        let log = logs.appendingPathComponent("launcher.log")
        if !fm.fileExists(atPath: log.path) { fm.createFile(atPath: log.path, contents: nil) }
        let output = try FileHandle(forWritingTo: log)
        try output.seekToEnd()
        self.output = output
        server.standardOutput = output
        server.standardError = output
        server.terminationHandler = { [weak self] process in
            DispatchQueue.main.async { self?.onExit?(process.terminationStatus) }
        }
        try server.run()
        process = server
    }

    func stop(_ completion: @escaping () -> Void) {
        guard let process else {
            DispatchQueue.main.async { completion() }
            return
        }
        if process.isRunning { process.terminate() }
        DispatchQueue.global().async {
            let deadline = Date().addingTimeInterval(30)
            let group = -process.processIdentifier
            while (process.isRunning || Darwin.kill(group, 0) == 0) && Date() < deadline {
                Thread.sleep(forTimeInterval: 0.1)
            }
            if Darwin.kill(group, 0) == 0 {
                // The bundled entry point puts the server and its workers in
                // their own group, so a stuck child cannot outlive Quit.
                Darwin.kill(group, SIGKILL)
            }
            if process.isRunning { Darwin.kill(process.processIdentifier, SIGKILL) }
            process.waitUntilExit()
            DispatchQueue.main.async { completion() }
        }
    }

    deinit {
        if lock >= 0 { Darwin.close(lock) }
        try? output?.close()
    }
}

// A browser-owned WebSocket stays open in background tabs and closes when the
// tab or browser closes. It is independent of backend restarts and polling.
final class BrowserSession {
    let token: String
    private let listener: NWListener
    private(set) var url: URL?
    private var connections: [UUID: NWConnection] = [:]
    private var active: Set<UUID> = []
    private var closeTimer: DispatchWorkItem?
    private var stopped = false
    var onLastTabClosed: (() -> Void)?
    var onFailure: ((Error) -> Void)?

    init() throws {
        let token = "kapowarr-\(UUID().uuidString)"
        self.token = token
        let websocket = NWProtocolWebSocket.Options()
        websocket.autoReplyPing = true
        websocket.maximumMessageSize = 1024
        websocket.setClientRequestHandler(.main) { protocols, _ in
            let valid = protocols.contains(token)
            return NWProtocolWebSocket.Response(
                status: valid ? .accept : .reject, subprotocol: valid ? token : nil
            )
        }
        let parameters = NWParameters.tcp
        parameters.requiredLocalEndpoint = .hostPort(host: "127.0.0.1", port: .any)
        parameters.defaultProtocolStack.applicationProtocols.insert(websocket, at: 0)
        listener = try NWListener(using: parameters)
    }

    func start(_ ready: @escaping () -> Void) {
        listener.stateUpdateHandler = { [weak self] state in
            guard let self, !self.stopped else { return }
            switch state {
            case .ready:
                guard let port = self.listener.port else { return }
                self.url = URL(string: "ws://127.0.0.1:\(port.rawValue)/")
                ready()
            case .failed(let error): self.onFailure?(error)
            default: break
            }
        }
        listener.newConnectionHandler = { [weak self] connection in self?.accept(connection) }
        listener.start(queue: .main)
    }

    private func accept(_ connection: NWConnection) {
        let id = UUID()
        connections[id] = connection
        connection.stateUpdateHandler = { [weak self] state in
            guard let self, !self.stopped else { return }
            switch state {
            case .ready:
                self.active.insert(id)
                self.closeTimer?.cancel()
                self.receive(connection, id: id)
            case .failed, .cancelled: self.closed(id)
            default: break
            }
        }
        connection.start(queue: .main)
    }

    private func receive(_ connection: NWConnection, id: UUID) {
        connection.receiveMessage { [weak self] data, context, complete, error in
            guard let self, !self.stopped else { return }
            let metadata = context?.protocolMetadata(definition: NWProtocolWebSocket.definition) as? NWProtocolWebSocket.Metadata
            if error != nil || metadata?.opcode == .close || (complete && data == nil && context == nil) {
                self.closed(id)
            } else {
                self.receive(connection, id: id)
            }
        }
    }

    private func closed(_ id: UUID) {
        connections.removeValue(forKey: id)?.cancel()
        guard active.remove(id) != nil, active.isEmpty, !stopped else { return }
        closeTimer?.cancel()
        let timer = DispatchWorkItem { [weak self] in
            guard let self, self.active.isEmpty, !self.stopped else { return }
            self.onLastTabClosed?()
        }
        closeTimer = timer
        DispatchQueue.main.asyncAfter(deadline: .now() + 5, execute: timer)
    }

    func stop() {
        stopped = true
        closeTimer?.cancel()
        listener.cancel()
        for connection in connections.values { connection.cancel() }
        connections.removeAll()
        active.removeAll()
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    let server = ServerController()
    var item: NSStatusItem!
    let status = NSMenuItem(title: "Starting Kapowarr…", action: nil, keyEquivalent: "")
    var timer: Timer?
    var starting = true
    var stopping = false
    var checking = false
    var deadline = Date().addingTimeInterval(120)
    var browserSession: BrowserSession?

    func applicationDidFinishLaunching(_ notification: Notification) {
        item = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
        item.button?.image = NSImage(systemSymbolName: "books.vertical", accessibilityDescription: "Kapowarr")
        let menu = NSMenu()
        menu.addItem(status)
        menu.addItem(.separator())
        menu.addItem(withTitle: "Open Kapowarr", action: #selector(openKapowarr), keyEquivalent: "o").target = self
        menu.addItem(withTitle: "View Logs", action: #selector(viewLogs), keyEquivalent: "l").target = self
        menu.addItem(withTitle: "Download Updates…", action: #selector(downloadUpdates), keyEquivalent: "").target = self
        menu.addItem(.separator())
        menu.addItem(withTitle: "Quit Kapowarr", action: #selector(quit), keyEquivalent: "q").target = self
        item.menu = menu
        server.onExit = { [weak self] code in
            guard let self, !self.stopping else { return }
            if code != 0 { self.showError("Kapowarr stopped unexpectedly. Open View Logs for details.") }
            self.quit()
        }
        do {
            let session = try BrowserSession()
            browserSession = session
            session.onLastTabClosed = { [weak self] in
                guard let self else { return }
                do {
                    if try self.server.quitOnBrowserClose() { self.quit() }
                } catch {
                    self.showError(error.localizedDescription)
                }
            }
            session.onFailure = { [weak self] error in
                self?.showError(error.localizedDescription)
                self?.quit()
            }
            session.start { [weak self, weak session] in
                guard let self, let session else { return }
                do {
                    try self.server.start(browserSession: session)
                    if CommandLine.arguments.contains("--browser-session-app-test") {
                        print("SERVER_PID=\(self.server.process!.processIdentifier)")
                        fflush(stdout)
                    }
                    self.timer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in self?.checkServer() }
                    self.checkServer()
                } catch {
                    self.showError(error.localizedDescription)
                    self.quit()
                }
            }
        } catch {
            showError(error.localizedDescription)
            quit()
        }
    }

    func checkServer() {
        guard !checking, !stopping, let url = try? server.serverURL() else { return }
        checking = true
        var request = URLRequest(url: url)
        request.timeoutInterval = 2
        URLSession.shared.dataTask(with: request) { [weak self] _, response, _ in
            DispatchQueue.main.async {
                guard let self, !self.stopping else { return }
                self.checking = false
                if let response = response as? HTTPURLResponse, response.statusCode == 200 {
                    self.status.title = "Kapowarr is running"
                    if self.starting {
                        self.starting = false
                        if !CommandLine.arguments.contains("--browser-session-app-test") {
                            NSWorkspace.shared.open(url)
                        }
                    }
                } else if self.starting && Date() > self.deadline {
                    self.starting = false
                    self.showError("Kapowarr is taking longer than expected to start. View Logs has the startup details. The app will keep running.")
                } else if !self.starting {
                    self.status.title = "Kapowarr is restarting…"
                }
            }
        }.resume()
    }

    @objc func openKapowarr() {
        if let url = try? server.serverURL() { NSWorkspace.shared.open(url) }
    }
    @objc func viewLogs() { NSWorkspace.shared.open(server.logs) }
    @objc func downloadUpdates() {
        NSWorkspace.shared.open(URL(string: "https://github.com/llithium/Kapowarr/releases")!)
    }
    @objc func quit() {
        // AppKit's deferred termination runs a nested event loop. Enter it
        // outside a main-dispatch callback so shutdown replies can run there.
        NSApp.perform(#selector(NSApplication.terminate(_:)), with: nil, afterDelay: 0)
    }

    func showError(_ message: String) {
        NSApp.activate(ignoringOtherApps: true)
        let alert = NSAlert()
        alert.messageText = "Kapowarr"
        alert.informativeText = message
        alert.addButton(withTitle: "OK")
        alert.addButton(withTitle: "View Logs")
        if alert.runModal() == .alertSecondButtonReturn { viewLogs() }
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        openKapowarr()
        return false
    }

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        guard !stopping else { return .terminateLater }
        stopping = true
        timer?.invalidate()
        browserSession?.stop()
        status.title = "Stopping Kapowarr…"
        server.stop { sender.reply(toApplicationShouldTerminate: true) }
        return .terminateLater
    }
}

// Exercise the same supervisor without opening a browser or a menu during CI.
if CommandLine.arguments.dropFirst().first == "--smoke-test" {
    let controller = ServerController()
    var session: BrowserSession?
    var finished = false
    var failure: Error?
    controller.onExit = { _ in finished = true }
    do {
        let start = {
            do {
                try controller.start(browserSession: session)
                print("SERVER_PID=\(controller.process!.processIdentifier)")
                fflush(stdout)
            } catch { failure = error; finished = true }
        }
        if CommandLine.arguments.contains("--browser-session") {
            session = try BrowserSession()
            session?.onLastTabClosed = { finished = true }
            session?.onFailure = { error in failure = error; finished = true }
            session?.start(start)
        } else { start() }
        let seconds = Double(CommandLine.arguments.last ?? "") ?? 15
        let deadline = Date().addingTimeInterval(seconds)
        while !finished && Date() < deadline {
            RunLoop.current.run(until: Date().addingTimeInterval(0.1))
        }
        session?.stop()
        var stopped = false
        controller.stop { stopped = true }
        while !stopped { RunLoop.current.run(until: Date().addingTimeInterval(0.1)) }
        if let failure { throw failure }
        print("Server stopped.")
    } catch {
        fputs("\(error.localizedDescription)\n", stderr)
        exit(1)
    }
} else {
    let app = NSApplication.shared
    let delegate = AppDelegate()
    app.setActivationPolicy(.accessory)
    app.delegate = delegate
    app.run()
}
