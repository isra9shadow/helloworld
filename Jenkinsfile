pipeline {
  agent any

  options {
    timestamps()
  }

  environment {
    // Python 3.11 (ruta absoluta; evita problemas)
    PYTHON_EXE = 'C:\\Users\\Israel\\AppData\\Local\\Programs\\Python\\Python311\\python.exe'

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
          Write-Host "=== Python ==="
          & "${env.PYTHON_EXE}" --version
          & "${env.PYTHON_EXE}" -c "import sys; print(sys.executable)"
          Write-Host "=== Java ==="
          java -version
        """
      }
    }

    stage('Unit') {
      steps {
        powershell """
          \$ErrorActionPreference = 'Stop'
          & "${env.PYTHON_EXE}" -m pytest --junitxml=result-unit.xml test\\unit
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

          function Wait-Port([int]\$port, [int]\$seconds) {
            \$deadline = (Get-Date).AddSeconds(\$seconds)
            while ((Get-Date) -lt \$deadline) {
              try {
                \$client = New-Object System.Net.Sockets.TcpClient
                \$iar = \$client.BeginConnect('${env.FLASK_HOST}', \$port, \$null, \$null)
                if (\$iar.AsyncWaitHandle.WaitOne(300)) {
                  \$client.EndConnect(\$iar)
                  \$client.Close()
                  return
                }
                \$client.Close()
              } catch { }
              Start-Sleep -Milliseconds 300
            }
            throw "Timeout waiting for port \$port"
          }

          # ---- Ensure Wiremock JAR exists (download if missing) ----
          New-Item -ItemType Directory -Force -Path "${env.WM_DIR}" | Out-Null
          if (!(Test-Path "${env.WM_JAR}")) {
            Write-Host "Downloading Wiremock..."
            Invoke-WebRequest -Uri "${env.WM_URL}" -OutFile "${env.WM_JAR}"
          }

          # ---- Start Wiremock (background) ----
          \$wm = Start-Process -FilePath "java" -ArgumentList "-jar","${env.WM_JAR}","--port","${env.WIREMOCK_PORT}","--root-dir","test\\wiremock" -PassThru -WindowStyle Hidden
          \$wm.Id | Out-File -Encoding ascii "${env.WIREMOCK_PID_FILE}"

          # ---- Start Flask (background) ----
          \$fl = Start-Process -FilePath "${env.PYTHON_EXE}" -ArgumentList "-m","flask","--app","app/api.py","run","--host","${env.FLASK_HOST}","--port","${env.FLASK_PORT}" -PassThru -WindowStyle Hidden
          \$fl.Id | Out-File -Encoding ascii "${env.FLASK_PID_FILE}"

          # ---- Wait services ----
          Wait-Port ${env.WIREMOCK_PORT} 25
          Wait-Port ${env.FLASK_PORT} 25

          # ---- Run REST tests ----
          & "${env.PYTHON_EXE}" -m pytest --junitxml=result-rest.xml test\\rest
        """
      }
      post {
        always {
          powershell """
            \$ErrorActionPreference = 'SilentlyContinue'

            if (Test-Path "${env.FLASK_PID_FILE}") {
              \$pid = Get-Content "${env.FLASK_PID_FILE}"
              Stop-Process -Id \$pid -Force -ErrorAction SilentlyContinue
              Remove-Item "${env.FLASK_PID_FILE}" -Force -ErrorAction SilentlyContinue
            }

            if (Test-Path "${env.WIREMOCK_PID_FILE}") {
              \$pid = Get-Content "${env.WIREMOCK_PID_FILE}"
              Stop-Process -Id \$pid -Force -ErrorAction SilentlyContinue
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
