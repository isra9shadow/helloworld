pipeline {
  agent any

  options {
    timestamps()
  }

  environment {
    PY = 'py -3.11'

    FLASK_HOST = '127.0.0.1'
    FLASK_PORT = '5000'
    WIREMOCK_PORT = '9090'

    FLASK_PID_FILE = 'flask.pid'
    WIREMOCK_PID_FILE = 'wiremock.pid'

    WM_DIR = 'tools\\wiremock'
    WM_JAR = 'tools\\wiremock\\wiremock-standalone-3.13.2.jar'
    WM_URL = 'https://repo1.maven.org/maven2/org/wiremock/wiremock-standalone/3.13.2/wiremock-standalone-3.13.2.jar'
  }

  stages {

    stage('Checkout') {
      steps {
        checkout scm
      }
    }

    stage('Diagnostico') {
      steps {
        powershell """
          \$ErrorActionPreference = 'Stop'
          Write-Host "=== WHOAMI ==="
          whoami

          Write-Host "=== PY LAUNCHER ==="
          py -0p

          Write-Host "=== PYTHON (FORZADO) ==="
          ${env.PY} --version
          ${env.PY} -c "import sys; print(sys.executable)"

          Write-Host "=== JAVA ==="
          java -version
        """
      }
    }

    stage('Unit') {
      steps {
        powershell """
          \$ErrorActionPreference = 'Stop'
          ${env.PY} -m pytest --junitxml=result-unit.xml test\\unit
        """
      }
      post {
        always {
          junit allowEmptyResults: true, testResults: 'result-unit.xml'
          archiveArtifacts allowEmptyArchive: true, artifacts: 'result-unit.xml'
        }
      }
    }

    stage('REST') {
      steps {
        powershell """
          \$ErrorActionPreference = 'Stop'

          function Wait-Http([string]\$url, [int]\$seconds) {
            \$deadline = (Get-Date).AddSeconds(\$seconds)
            while ((Get-Date) -lt \$deadline) {
              try {
                Invoke-WebRequest -Uri \$url -UseBasicParsing -TimeoutSec 2 | Out-Null
                return
              } catch { }
              Start-Sleep -Milliseconds 400
            }
            throw "Timeout esperando respuesta HTTP en: \$url"
          }

          function Wait-Port([int]\$port, [int]\$seconds) {
            \$deadline = (Get-Date).AddSeconds(\$seconds)
            while ((Get-Date) -lt \$deadline) {
              try {
                \$c = New-Object System.Net.Sockets.TcpClient
                \$iar = \$c.BeginConnect('${env.FLASK_HOST}', \$port, \$null, \$null)
                if (\$iar.AsyncWaitHandle.WaitOne(300)) {
                  \$c.EndConnect(\$iar)
                  \$c.Close()
                  return
                }
                \$c.Close()
              } catch { }
              Start-Sleep -Milliseconds 300
            }
            throw "Timeout esperando puerto: \$port"
          }

          # --- Preparar WireMock jar (en tools\\wiremock) ---
          New-Item -ItemType Directory -Force -Path "${env.WM_DIR}" | Out-Null
          if (!(Test-Path "${env.WM_JAR}")) {
            Write-Host "Descargando WireMock..."
            Invoke-WebRequest -Uri "${env.WM_URL}" -OutFile "${env.WM_JAR}" -UseBasicParsing
          }

          # --- Arrancar WireMock (background) ---
          # root-dir: donde están mappings/ (tu repo tiene test\\wiremock\\mappings)
          \$wmProc = Start-Process -FilePath "java" -ArgumentList @(
            "-jar","${env.WM_JAR}",
            "--port","${env.WIREMOCK_PORT}",
            "--root-dir","test\\wiremock",
            "--verbose"
          ) -PassThru -WindowStyle Hidden

          \$wmProc.Id | Out-File -Encoding ascii "${env.WIREMOCK_PID_FILE}"
          Write-Host "WireMock PID: \$("\$wmProc.Id")"

          # --- Arrancar Flask (background) ---
          # Usamos -m flask para levantar el microservicio
          \$flProc = Start-Process -FilePath "cmd.exe" -ArgumentList @(
            "/c",
            "${env.PY} -m flask --app app/api.py run --host ${env.FLASK_HOST} --port ${env.FLASK_PORT}"
          ) -PassThru -WindowStyle Hidden

          \$flProc.Id | Out-File -Encoding ascii "${env.FLASK_PID_FILE}"
          Write-Host "Flask PID: \$("\$flProc.Id")"

          # --- Esperar servicios ---
          Wait-Port ${env.WIREMOCK_PORT} 30
          Wait-Port ${env.FLASK_PORT} 30

          # Opcional (más fiable): comprobar endpoints si existen
          # Flask: /health podría no existir; por eso no lo fuerzo.
          # WireMock: /__admin suele responder
          Wait-Http "http://${env.FLASK_HOST}:${env.WIREMOCK_PORT}/__admin" 30

          # --- Ejecutar tests REST ---
          ${env.PY} -m pytest --junitxml=result-rest.xml test\\rest
        """
      }

      post {
        always {
          powershell """
            \$ErrorActionPreference = 'SilentlyContinue'

            if (Test-Path "${env.FLASK_PID_FILE}") {
              \$procId = Get-Content "${env.FLASK_PID_FILE}"
              Stop-Process -Id \$procId -Force -ErrorAction SilentlyContinue
              Remove-Item "${env.FLASK_PID_FILE}" -Force -ErrorAction SilentlyContinue
            }

            if (Test-Path "${env.WIREMOCK_PID_FILE}") {
              \$procId = Get-Content "${env.WIREMOCK_PID_FILE}"
              Stop-Process -Id \$procId -Force -ErrorAction SilentlyContinue
              Remove-Item "${env.WIREMOCK_PID_FILE}" -Force -ErrorAction SilentlyContinue
            }
          """
          junit allowEmptyResults: true, testResults: 'result-rest.xml'
          archiveArtifacts allowEmptyArchive: true, artifacts: 'result-rest.xml'
        }
      }
    }
  }
}
