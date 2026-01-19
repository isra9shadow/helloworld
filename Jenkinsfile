pipeline {
  agent any

  options { timestamps() }

  environment {
    // Python sin rutas absolutas
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
      steps { checkout scm }
    }

    // ===================== UNIT (igual que tu base) =====================
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

    // ===================== REST (igual que tu base, con Resolve-JavaExe) =====================
    stage('REST') {
      steps {
        powershell """
          \$ErrorActionPreference = 'Stop'

          function Wait-Port([int]\$port, [int]\$seconds) {
            \$deadline = (Get-Date).AddSeconds(\$seconds)
            while ((Get-Date) -lt \$deadline) {
              try {
                \$c = New-Object System.Net.Sockets.TcpClient
                \$iar = \$c.BeginConnect('${env.FLASK_HOST}', \$port, \$null, \$null)
                if (\$iar.AsyncWaitHandle.WaitOne(300)) {
                  \$c.EndConnect(\$iar); \$c.Close(); return
                }
                \$c.Close()
              } catch { }
              Start-Sleep -Milliseconds 300
            }
            throw "Timeout esperando puerto: \$port"
          }

          function Resolve-JavaExe {
            \$candidates = New-Object System.Collections.Generic.List[string]

            # 1) JAVA_HOME si existe
            if (\$env:JAVA_HOME) {
              \$p = Join-Path \$env:JAVA_HOME 'bin\\java.exe'
              if (Test-Path \$p) { \$candidates.Add(\$p) }
            }

            # 2) Get-Command java
            try {
              \$cmd = Get-Command java -ErrorAction Stop
              if (\$cmd -and \$cmd.Source -and (Test-Path \$cmd.Source)) { \$candidates.Add(\$cmd.Source) }
            } catch { }

            # 3) where.exe java
            try {
              \$lines = & where.exe java 2>\$null
              if (\$LASTEXITCODE -eq 0 -and \$lines) {
                \$lines | ForEach-Object { if (Test-Path \$_) { \$candidates.Add(\$_) } }
              }
            } catch { }

            # 4) Carpetas típicas
            \$roots = @(
              'C:\\Program Files\\Eclipse Adoptium',
              'C:\\Program Files\\Java'
            )

            foreach (\$r in \$roots) {
              if (Test-Path \$r) {
                Get-ChildItem \$r -Directory -ErrorAction SilentlyContinue |
                  Sort-Object Name -Descending |
                  ForEach-Object {
                    \$p = Join-Path \$_.FullName 'bin\\java.exe'
                    if (Test-Path \$p) { \$candidates.Add(\$p) }
                  }
              }
            }

            \$javaExe = \$candidates | Select-Object -Unique | Select-Object -First 1
            if (-not \$javaExe) { throw 'No se encuentra Java (java.exe). Configura JAVA_HOME o instala un JDK (Temurin/Adoptium).' }
            return \$javaExe
          }

          \$javaExe = Resolve-JavaExe

          # --- WireMock jar ---
          New-Item -ItemType Directory -Force -Path "${env.WM_DIR}" | Out-Null
          if (!(Test-Path "${env.WM_JAR}")) {
            Invoke-WebRequest -Uri "${env.WM_URL}" -OutFile "${env.WM_JAR}" -UseBasicParsing
          }

          # --- Start WireMock ---
          \$wmProc = Start-Process -FilePath \$javaExe -ArgumentList @(
            "-jar","${env.WM_JAR}",
            "--port","${env.WIREMOCK_PORT}",
            "--root-dir","test\\wiremock"
          ) -PassThru -WindowStyle Hidden
          \$wmProc.Id | Out-File -Encoding ascii "${env.WIREMOCK_PID_FILE}"

          # --- Start Flask ---
          \$flProc = Start-Process -FilePath "cmd.exe" -ArgumentList @(
            "/c",
            "${env.PY} -m flask --app app/api.py run --host ${env.FLASK_HOST} --port ${env.FLASK_PORT}"
          ) -PassThru -WindowStyle Hidden
          \$flProc.Id | Out-File -Encoding ascii "${env.FLASK_PID_FILE}"

          Wait-Port ${env.WIREMOCK_PORT} 30
          Wait-Port ${env.FLASK_PORT} 30

          ${env.PY} -m pytest --junitxml=result-rest.xml test\\rest
        """
      }

      post {
        always {
          powershell """
            \$ErrorActionPreference = 'SilentlyContinue'

            if (Test-Path "${env.FLASK_PID_FILE}") {
              \$flaskId = Get-Content "${env.FLASK_PID_FILE}"
              Stop-Process -Id \$flaskId -Force -ErrorAction SilentlyContinue
              Remove-Item "${env.FLASK_PID_FILE}" -Force -ErrorAction SilentlyContinue
            }

            if (Test-Path "${env.WIREMOCK_PID_FILE}") {
              \$wmId = Get-Content "${env.WIREMOCK_PID_FILE}"
              Stop-Process -Id \$wmId -Force -ErrorAction SilentlyContinue
              Remove-Item "${env.WIREMOCK_PID_FILE}" -Force -ErrorAction SilentlyContinue
            }
          """
          junit allowEmptyResults: true, testResults: 'result-rest.xml'
          archiveArtifacts allowEmptyArchive: true, artifacts: 'result-rest.xml'
        }
      }
    }

    // ===================== AÑADIDOS CP1.2 RETO 1 =====================

    stage('Static (flake8)') {
      steps {
        powershell """
          \$ErrorActionPreference = 'Stop'
          ${env.PY} -m flake8 app test
        """
      }
    }

    stage('Security Test (bandit)') {
      steps {
        powershell """
          \$ErrorActionPreference = 'Stop'
          ${env.PY} -m bandit -r app
        """
      }
    }

    stage('Coverage (Cobertura)') {
      steps {
        powershell """
          \$ErrorActionPreference = 'Stop'
          ${env.PY} -m coverage run -m pytest test\\unit
          ${env.PY} -m coverage xml -o coverage.xml
          ${env.PY} -m coverage report -m
        """
      }
      post {
        always {
          cobertura coberturaReportFile: 'coverage.xml',
                    autoUpdateHealth: false,
                    autoUpdateStability: false,
                    failNoReports: false
          archiveArtifacts allowEmptyArchive: true, artifacts: 'coverage.xml'
        }
      }
    }
  }
}
