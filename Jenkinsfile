pipeline {
  agent any

  options { timestamps() }

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

    FLAKE8_REPORT = 'flake8.log'
    BANDIT_REPORT = 'bandit.json'

    UNIT_JUNIT = 'result-unit.xml'
    REST_JUNIT = 'result-rest.xml'

    COVERAGE_XML = 'coverage.xml'

    JMETER_JMX_BASE = 'test\\jmeter\\flask.jmx'
    JMETER_JMX = 'flask_cp12.jmx'
    JMETER_JTL = 'jmeter.jtl'
  }

  stages {

    stage('Checkout') {
      steps { checkout scm }
    }

    stage('Unit') {
      steps {
        powershell """
          \$ErrorActionPreference = 'Stop'

          # Unit tests (UNA sola vez) + cobertura
          ${env.PY} -m coverage erase
          ${env.PY} -m coverage run --branch --source app -m pytest --junitxml=${env.UNIT_JUNIT} test\\unit
          ${env.PY} -m coverage xml -o ${env.COVERAGE_XML}
          ${env.PY} -m coverage report -m
        """
      }
      post {
        always {
          junit allowEmptyResults: true, testResults: "${env.UNIT_JUNIT}"
          archiveArtifacts allowEmptyArchive: true, artifacts: "${env.UNIT_JUNIT},${env.COVERAGE_XML}"
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
                \$c = New-Object System.Net.Sockets.TcpClient
                \$iar = \$c.BeginConnect('${env.FLASK_HOST}', \$port, \$null, \$null)
                if (\$iar.AsyncWaitHandle.WaitOne(300)) { \$c.EndConnect(\$iar); \$c.Close(); return }
                \$c.Close()
              } catch { }
              Start-Sleep -Milliseconds 300
            }
            throw "Timeout esperando puerto: \$port"
          }

          function Resolve-JavaExe {
            \$candidates = New-Object System.Collections.Generic.List[string]
            if (\$env:JAVA_HOME) {
              \$p = Join-Path \$env:JAVA_HOME 'bin\\java.exe'
              if (Test-Path \$p) { \$candidates.Add(\$p) }
            }
            try {
              \$cmd = Get-Command java -ErrorAction Stop
              if (\$cmd -and \$cmd.Source -and (Test-Path \$cmd.Source)) { \$candidates.Add(\$cmd.Source) }
            } catch { }
            try {
              \$lines = & where.exe java 2>\$null
              if (\$LASTEXITCODE -eq 0 -and \$lines) { \$lines | ForEach-Object { if (Test-Path \$_) { \$candidates.Add(\$_) } } }
            } catch { }
            \$roots = @('C:\\Program Files\\Eclipse Adoptium','C:\\Program Files\\Java')
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

          ${env.PY} -m pytest --junitxml=${env.REST_JUNIT} test\\rest
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
          junit allowEmptyResults: true, testResults: "${env.REST_JUNIT}"
          archiveArtifacts allowEmptyArchive: true, artifacts: "${env.REST_JUNIT}"
        }
      }
    }

    stage('Static (Flake8)') {
      steps {
        script {
          // Ejecuta flake8 sin tumbar el stage por exit-code
          powershell(returnStatus: true, script: """
            \$ErrorActionPreference = 'Continue'
            ${env.PY} -m flake8 app test 2>&1 | Out-File -Encoding utf8 ${env.FLAKE8_REPORT}
            exit 0
          """)

          def txt = fileExists(env.FLAKE8_REPORT) ? readFile(env.FLAKE8_REPORT).trim() : ""
          int findings = (txt ? txt.split(/\r?\n/).findAll { it.trim() }.size() : 0)

          // Publica en Warnings-NG (gráficas de flake8)
          recordIssues tools: [flake8(pattern: env.FLAKE8_REPORT)]

          if (findings >= 10) {
            catchError(stageResult: 'FAILURE', buildResult: 'FAILURE') {
              error "Flake8: ${findings} hallazgos (>=10) => build UNHEALTHY (rojo), pero continúo."
            }
          } else if (findings >= 8) {
            catchError(stageResult: 'UNSTABLE', buildResult: 'UNSTABLE') {
              error "Flake8: ${findings} hallazgos (>=8) => build UNSTABLE (amarillo), pero continúo."
            }
          } else {
            echo "Flake8: ${findings} hallazgos (<8) => OK."
          }

          archiveArtifacts allowEmptyArchive: true, artifacts: "${env.FLAKE8_REPORT}"
        }
      }
    }

    stage('Security Test (Bandit)') {
      steps {
        script {
          powershell(returnStatus: true, script: """
            \$ErrorActionPreference = 'Continue'
            ${env.PY} -m bandit -r app -f json -o ${env.BANDIT_REPORT} 2>\$null
            exit 0
          """)

          def countStr = powershell(returnStdout: true, script: """
            if (Test-Path "${env.BANDIT_REPORT}") {
              (Get-Content "${env.BANDIT_REPORT}" -Raw | ConvertFrom-Json).results.Count
            } else {
              0
            }
          """).trim()

          int findings = countStr.isInteger() ? countStr.toInteger() : 0

          // Publica en Warnings-NG (gráficas de bandit)
          recordIssues tools: [bandit(pattern: env.BANDIT_REPORT)]

          if (findings >= 4) {
            catchError(stageResult: 'FAILURE', buildResult: 'FAILURE') {
              error "Bandit: ${findings} hallazgos (>=4) => build UNHEALTHY (rojo), pero continúo."
            }
          } else if (findings >= 2) {
            catchError(stageResult: 'UNSTABLE', buildResult: 'UNSTABLE') {
              error "Bandit: ${findings} hallazgos (>=2) => build UNSTABLE (amarillo), pero continúo."
            }
          } else {
            echo "Bandit: ${findings} hallazgos (<2) => OK."
          }

          archiveArtifacts allowEmptyArchive: true, artifacts: "${env.BANDIT_REPORT}"
        }
      }
    }

    stage('Performance (JMeter)') {
      steps {
        powershell """
          \$ErrorActionPreference = 'Stop'

          function Wait-Port([int]\$port, [int]\$seconds) {
            \$deadline = (Get-Date).AddSeconds(\$seconds)
            while ((Get-Date) -lt \$deadline) {
              try {
                \$c = New-Object System.Net.Sockets.TcpClient
                \$iar = \$c.BeginConnect('${env.FLASK_HOST}', \$port, \$null, \$null)
                if (\$iar.AsyncWaitHandle.WaitOne(300)) { \$c.EndConnect(\$iar); \$c.Close(); return }
                \$c.Close()
              } catch { }
              Start-Sleep -Milliseconds 300
            }
            throw "Timeout esperando puerto: \$port"
          }

          function Resolve-JMeterExe {
            # 1) JMETER_HOME
            if (\$env:JMETER_HOME) {
              \$p = Join-Path \$env:JMETER_HOME 'bin\\jmeter.bat'
              if (Test-Path \$p) { return \$p }
            }
            # 2) where.exe
            try {
              \$lines = & where.exe jmeter.bat 2>\$null
              if (\$LASTEXITCODE -eq 0 -and \$lines) { return \$lines[0] }
            } catch { }
            throw 'No se encuentra JMeter (jmeter.bat). Añade JMETER_HOME o mete jmeter en PATH.'
          }

          \$jmeterExe = Resolve-JMeterExe

          # Creamos un JMX temporal que cumpla: 5 hilos y 40 add + 40 substract.
          Copy-Item "${env.JMETER_JMX_BASE}" "${env.JMETER_JMX}" -Force
          (Get-Content "${env.JMETER_JMX}" -Raw) `
            -replace '<stringProp name="ThreadGroup.num_threads">\\d+</stringProp>','<stringProp name="ThreadGroup.num_threads">5</stringProp>' `
            -replace '<stringProp name="LoopController.loops">\\d+</stringProp>','<stringProp name="LoopController.loops">8</stringProp>' `
            | Set-Content "${env.JMETER_JMX}" -Encoding UTF8

          # Start Flask (Wiremock NO necesario en performance)
          \$flProc = Start-Process -FilePath "cmd.exe" -ArgumentList @(
            "/c",
            "${env.PY} -m flask --app app/api.py run --host ${env.FLASK_HOST} --port ${env.FLASK_PORT}"
          ) -PassThru -WindowStyle Hidden
          \$flProc.Id | Out-File -Encoding ascii "${env.FLASK_PID_FILE}"

          Wait-Port ${env.FLASK_PORT} 30

          # Ejecuta JMeter en modo no-GUI generando JTL para el plugin Performance
          & \$jmeterExe -n -t "${env.JMETER_JMX}" -l "${env.JMETER_JTL}"

          # Stop Flask
          if (Test-Path "${env.FLASK_PID_FILE}") {
            \$flaskId = Get-Content "${env.FLASK_PID_FILE}"
            Stop-Process -Id \$flaskId -Force -ErrorAction SilentlyContinue
            Remove-Item "${env.FLASK_PID_FILE}" -Force -ErrorAction SilentlyContinue
          }
        """
      }
      post {
        always {
          archiveArtifacts allowEmptyArchive: true, artifacts: "${env.JMETER_JTL},${env.JMETER_JMX}"
          perfReport sourceDataFiles: "${env.JMETER_JTL}"
        }
      }
    }

    stage('Coverage') {
      steps {
        script {
          // Publica Cobertura (necesita coverage.xml ya creado en Unit)
          cobertura coberturaReportFile: "${env.COVERAGE_XML}", failNoReports: false, autoUpdateHealth: false, autoUpdateStability: false

          def rates = powershell(returnStdout: true, script: """
            if (Test-Path "${env.COVERAGE_XML}") {
              [xml]\$x = Get-Content "${env.COVERAGE_XML}"
              \$line = [double]\$x.coverage.'line-rate' * 100
              \$branch = [double]\$x.coverage.'branch-rate' * 100
              "{0:N2};{1:N2}" -f \$line, \$branch
            } else {
              "0;0"
            }
          """).trim()

          def parts = rates.split(';')
          double linePct = parts[0].replace(',', '.') as double
          double branchPct = parts[1].replace(',', '.') as double

          echo "Coverage => Lines: ${linePct}%, Branches: ${branchPct}%"

          // Baremos CP1.2:
          // Lines: 85-95 unstable; >95 OK; <85 FAIL
          // Branch: 80-90 unstable; >90 OK; <80 FAIL
          boolean fail = (linePct < 85.0) || (branchPct < 80.0)
          boolean unstable = (!fail) && ((linePct >= 85.0 && linePct <= 95.0) || (branchPct >= 80.0 && branchPct <= 90.0))

          if (fail) {
            catchError(stageResult: 'FAILURE', buildResult: 'FAILURE') {
              error "Coverage por debajo de mínimos => FAIL (lines<85 o branches<80). Continúo."
            }
          } else if (unstable) {
            catchError(stageResult: 'UNSTABLE', buildResult: 'UNSTABLE') {
              error "Coverage en zona UNSTABLE (lines 85-95 o branches 80-90). Continúo."
            }
          } else {
            echo "Coverage OK (lines>95 y branches>90)."
          }
        }
      }
    }
  }
}
