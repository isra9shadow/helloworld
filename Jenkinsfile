pipeline {
  agent any

  options {
    timestamps()
  }

  environment {
    // Python (sin rutas locales): usamos el launcher con versión fijada
    PY = 'py -3.11'

    // Java (sin rutas de usuario): apuntamos al JDK 17 instalado en Program Files
    JAVA_HOME = 'C:\\Program Files\\Eclipse Adoptium\\jdk-17.0.17.10-hotspot'

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

    stage('Diagnostico (entorno Jenkins)') {
      steps {
        powershell """
          \$ErrorActionPreference = 'Stop'

          Write-Host "=== WHOAMI ==="
          whoami

          Write-Host "=== WORKSPACE ==="
          Write-Host \$env:WORKSPACE

          # Forzar Java 17 dentro del job (sin depender del PATH global del servicio)
          \$env:JAVA_HOME = '${env.JAVA_HOME}'
          \$env:Path = "\$env:JAVA_HOME\\bin;\$env:Path"

          Write-Host "=== JAVA_HOME ==="
          Write-Host \$env:JAVA_HOME

          Write-Host "=== JAVA (resuelto) ==="
          Get-Command java | Format-List -Property Source
          java -version

          Write-Host "=== PY LAUNCHER LIST ==="
          py -0p

          Write-Host "=== PY (FORZADO) ==="
          ${env.PY} --version
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

    stage('REST (Flask + WireMock + tests)') {
      steps {
        powershell """
          \$ErrorActionPreference = 'Stop'

          # Forzar Java 17 dentro del job (sin depender del PATH global del servicio)
          \$env:JAVA_HOME = '${env.JAVA_HOME}'
          \$env:Path = "\$env:JAVA_HOME\\bin;\$env:Path"

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

          # --- Preparar WireMock jar ---
          New-Item -ItemType Directory -Force -Path "${env.WM_DIR}" | Out-Null
          if (!(Test-Path "${env.WM_JAR}")) {
            Write-Host "Descargando WireMock..."
            Invoke-WebRequest -Uri "${env.WM_URL}" -OutFile "${env.WM_JAR}" -UseBasicParsing
          }

          # --- Arrancar WireMock (background) ---
          \$wmProc = Start-Process -FilePath "java" -ArgumentList @(
            "-jar","${env.WM_JAR}",
            "--port","${env.WIREMOCK_PORT}",
            "--root-dir","test\\wiremock"
          ) -PassThru -WindowStyle Hidden

          \$wmProc.Id | Out-File -Encoding ascii "${env.WIREMOCK_PID_FILE}"
          Write-Host "WireMock PID: \$("\$wmProc.Id")"

          # --- Arrancar Flask (background) ---
          # Nota: usamos cmd.exe para ejecutar el comando con 'py -3.11 ...'
          \$flProc = Start-Process -FilePath "cmd.exe" -ArgumentList @(
            "/c",
            "${env.PY} -m flask --app app/api.py run --host ${env.FLASK_HOST} --port ${env.FLASK_PORT}"
          ) -PassThru -WindowStyle Hidden

          \$flProc.Id | Out-File -Encoding ascii "${env.FLASK_PID_FILE}"
          Write-Host "Flask PID: \$("\$flProc.Id")"

          # --- Esperar servicios ---
          Wait-Port ${env.WIREMOCK_PORT} 30
          Wait-Port ${env.FLASK_PORT} 30

          # --- Ejecutar tests REST ---
          ${env.PY} -m pytest --junitxml=result-rest.xml test\\rest
        """
      }

      post {
        always {
          powershell """
            \$ErrorActionPreference = 'SilentlyContinue'

            # Parar Flask
            if (Test-Path "${env.FLASK_PID_FILE}") {
              \$procId = Get-Content "${env.FLASK_PID_FILE}"
              Stop-Process -Id \$procId -Force -ErrorAction SilentlyContinue
              Remove-Item "${env.FLASK_PID_FILE}" -Force -ErrorAction SilentlyContinue
            }

            # Parar WireMock
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
