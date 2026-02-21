const { app, BrowserWindow } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const http = require('http');

// Prevent EPIPE errors from crashing the app
process.on('uncaughtException', (err) => {
    if (err.code === 'EPIPE') {
        // Silently ignore EPIPE errors (broken pipe)
        return;
    }
    console.error('Uncaught Exception:', err);
});

process.stdout.on('error', (err) => {
    if (err.code !== 'EPIPE') {
        console.error('stdout error:', err);
    }
});

process.stderr.on('error', (err) => {
    if (err.code !== 'EPIPE') {
        console.error('stderr error:', err);
    }
});

let mainWindow;
let backendProcess;
const BACKEND_PORT = 8000;
const FRONTEND_PORT = 5173;

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1280,
        height: 860,
        backgroundColor: '#0f172a', // Matches index.css --bg-primary
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false,
        },
    });

    // In development, load from Vite server. In production, load file.
    // We can detect dev mode by checking if we are running from a script with 'electron .'
    const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged;

    // FORCE DEV MODE: Always load from localhost to ensure latest code
    console.log(`Loading frontend from http://localhost:${FRONTEND_PORT}`);
    mainWindow.loadURL(`http://localhost:${FRONTEND_PORT}`);
    mainWindow.webContents.openDevTools();
    // if (isDev) {
    //     console.log(`Loading frontend from http://localhost:${FRONTEND_PORT}`);
    //     // Add a small delay or retry to ensure Vite is up? 
    //     // 'concurrently' and 'wait-on' in package.json will handle the initial wait.
    //     mainWindow.loadURL(`http://localhost:${FRONTEND_PORT}`);
    //     mainWindow.webContents.openDevTools();
    // } else {
    //     mainWindow.loadFile(path.join(__dirname, 'dist', 'index.html'));
    // }

    mainWindow.on('closed', () => {
        mainWindow = null;
    });
}

function startBackend() {
    const backendPath = path.join(__dirname, 'backend');
    console.log('Starting Python Backend from:', backendPath);

    // Using 'python3' - ensure the user has this in their PATH.
    // In a packaged app, this would be the path to the bundled executable.
    backendProcess = spawn('python3', ['-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', `${BACKEND_PORT}`], {
        cwd: backendPath,
        shell: true, // Helpful for finding commands in path
    });

    // Limit console output to prevent EPIPE errors
    let logCount = 0;
    const MAX_LOGS = 50; // Only show first 50 log lines

    backendProcess.stdout.on('data', (data) => {
        if (logCount < MAX_LOGS) {
            try {
                console.log(`[Backend]: ${data.toString().substring(0, 200)}`); // Limit line length
                logCount++;
            } catch (err) {
                // Silently ignore EPIPE errors
            }
        }
    });

    backendProcess.stderr.on('data', (data) => {
        if (logCount < MAX_LOGS) {
            try {
                console.error(`[Backend Error]: ${data.toString().substring(0, 200)}`);
                logCount++;
            } catch (err) {
                // Silently ignore EPIPE errors
            }
        }
    });

    backendProcess.on('close', (code) => {
        try {
            console.log(`Backend process exited with code ${code}`);
        } catch (err) {
            // Silently ignore EPIPE errors
        }
    });

    // Handle errors on stdout/stderr to prevent crashes
    backendProcess.stdout.on('error', (err) => {
        if (err.code !== 'EPIPE') {
            console.error('Backend stdout error:', err);
        }
    });

    backendProcess.stderr.on('error', (err) => {
        if (err.code !== 'EPIPE') {
            console.error('Backend stderr error:', err);
        }
    });
}

function killBackend() {
    if (backendProcess) {
        console.log('Stopping backend...');
        // On Windows, tree-kill might be needed. On Mac, kill() usually works for spawn/shell.
        backendProcess.kill();
        backendProcess = null;
    }
}

app.whenReady().then(async () => {
    startBackend();
    // Wait for backend to be reachable before loading the frontend
    const http = require('http');
    const waitForBackend = () => new Promise((resolve) => {
        const check = () => {
            http.get('http://127.0.0.1:8000/docs', (res) => {
                if (res.statusCode === 200) {
                    resolve();
                } else {
                    setTimeout(check, 200);
                }
            }).on('error', () => setTimeout(check, 200));
        };
        check();
    });
    await waitForBackend();
    createWindow();

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            createWindow();
        }
    });
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

app.on('will-quit', () => {
    killBackend();
});
