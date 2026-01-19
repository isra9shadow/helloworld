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

    BANDIT_JSON = 'bandit.json'
    BANDIT_LOG  = 'bandit.log'   // lo parseamos como PEP8 (warnings-ng)

    UNIT_JUNIT = 'result-unit.xml'
    REST_JUNIT = 'result-rest.xml'

    COVERAGE_XML = 'coverage.xml'

    JMETER_JMX_BASE = 'test\\jmeter\\flask.jmx'
    JMETER_JMX = 'flask_cp12.jmx'
    JMETER_JTL = 'jmeter.jtl'

    // JMeter (zip + extracción). JMeter requiere Java 8+.
    JMETER_DIR  = 'tools\\jmeter'
    JMETER_VER  = '5.6.3'
    JMETER_ZIP  = 'apache-jmeter-5.6.3.zip'
    JMETER_URL  = 'https://archive.apache.org/dist/jmeter/binaries/apache-jmeter-5.6.3.zip'
    JMETER_HOME = 'tools\\jmeter\\apache-jmeter-5.6.3'
    JMETER_BAT  = 'tools\\jmeter\\apache-jmeter-5.6.3\\bin\\jmeter.bat'
  }

  stages {

    stage('Checkout') {
      steps { checkout scm }
    }

    stage('Unit') {
      steps {
        // Debe ser "siempre verde" y solo se ejecuta una vez en todo el pipeline
        catchError(stageResult: 'SUCCESS', buildResult: 'SUCCESS') {
          powershell """
            \$ErrorActionPreference = 'Stop'
            ${env.PY} -m coverage erase
            ${env.PY} -m coverage run --branch --source app -m pytest --junitxml=${env.UNIT_JUNIT} test\\unit
            ${env.PY} -m coverage xml -o ${env.COVERAGE_XML}
            ${env.PY} -m coverage report -m
          """
        }
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
        // Sin baremo y no debe “romper” el pipeline
        catchError(stageResult: 'SUCCESS', buildResult: 'SUCCESS') {
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
              if (-not \$javaExe) { throw 'No se encuentra Java (java.exe).' }
              return \$javaExe
            }

            \$javaExe = Resolve-JavaExe

            New-Item -ItemType Directory -Force -Path "${env.WM_DIR}" | Out-Null
            if (!(Test-Path "${env.WM_JAR}")) {
              Invoke-WebRequest -Uri "${env.WM_URL}" -OutFile "${env.WM_JAR}" -UseBasicParsing
            }

            \$wmProc = Start-Process -FilePath \$javaExe -ArgumentList @(
              "-jar","${env.WM_JAR}",
              "--port","${env.WIREMOCK_PORT}",
              "--root-dir","test\\wiremock"
            ) -PassThru -WindowStyle Hidden
            \$wmProc.Id | Out-File -Encoding ascii "${env.WIREMOCK_PID_FILE}"

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
          powershell(returnStatus: true, script: """
            \$ErrorActionPreference = 'Continue'
            ${env.PY} -m flake8 app test 2>&1 | Out-File -Encoding utf8 ${env.FLAKE8_REPORT}
            exit 0
          """)

          def txt = fileExists(env.FLAKE8_REPORT) ? readFile(env.FLAKE8_REPORT).trim() : ""
          int findings = (txt ? txt.split(/\r?\n/).findAll { it.trim() }.size() : 0)

          recordIssues tools: [flake8(pattern: env.FLAKE8_REPORT)]
          archiveArtifacts allowEmptyArchive: true, artifacts: "${env.FLAKE8_REPORT}"

          if (findings >= 10) {
            catchError(stageResult: 'FAILURE', buildResult: 'FAILURE') {
              error "Flake8: ${findings} findings (>=10) => UNHEALTHY (rojo), pero el pipeline continúa."
            }
          } else if (findings >= 8) {
            catchError(stageResult: 'UNSTABLE', buildResult: 'UNSTABLE') {
              error "Flake8: ${findings} findings (>=8) => UNSTABLE (amarillo), pero el pipeline continúa."
            }
          } else {
            echo "Flake8: ${findings} findings (<8) => OK."
          }
        }
      }
    }

    stage('Security Test (Bandit)') {
      steps {
        script {
          powershell(returnStatus: true, script: """
            \$ErrorActionPreference = 'Continue'
            ${env.PY} -m bandit -r app -f json -o ${env.BANDIT_JSON} 2>\$null
            exit 0
          """)

          // Convertimos a formato "pep8" para warnings-ng
          powershell(returnStatus: true, script: """
            \$ErrorActionPreference = 'Continue'
            if (Test-Path "${env.BANDIT_JSON}") {
              \$j = Get-Content "${env.BANDIT_JSON}" -Raw | ConvertFrom-Json
              \$j.results | ForEach-Object {
                \$file = \$_.filename
                \$line = \$_.line_number
                \$code = \$_.test_id
                \$msg  = (\$_.issue_text -replace "`r|`n",' ') -replace ':','-'
                "\${file}:\${line}:1: \${code} \${msg}"
              } | Out-File -Encoding utf8 "${env.BANDIT_LOG}"
            } else {
              "" | Out-File -Encoding utf8 "${env.BANDIT_LOG}"
            }
            exit 0
          """)

          def countStr = powershell(returnStdout: true, script: """
            if (Test-Path "${env.BANDIT_JSON}") {
              (Get-Content "${env.BANDIT_JSON}" -Raw | ConvertFrom-Json).results.Count
            } else { 0 }
          """).trim()
          int findings = countStr.isInteger() ? countStr.toInteger() : 0

          echo "Bandit findings: ${findings}"
          recordIssues tools: [pep8(pattern: env.BANDIT_LOG)]
          archiveArtifacts allowEmptyArchive: true, artifacts: "${env.BANDIT_JSON},${env.BANDIT_LOG}"

          if (findings >= 4) {
            catchError(stageResult: 'FAILURE', buildResult: 'FAILURE') {
              error "Bandit: ${findings} findings (>=4) => UNHEALTHY (rojo), pero el pipeline continúa."
            }
          } else if (findings >= 2) {
            catchError(stageResult: 'UNSTABLE', buildResult: 'UNSTABLE') {
              error "Bandit: ${findings} findings (>=2) => UNSTABLE (amarillo), pero el pipeline continúa."
            }
          } else {
            echo "Bandit: ${findings} findings (<2) => OK."
          }
        }
      }
    }

    stage('Performance (JMeter)') {
      steps {
        script {
          // No hay baremo, pero queremos que el pipeline continúe incluso si falla
          catchError(stageResult: 'FAILURE', buildResult: 'FAILURE') {
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
                if (-not \$javaExe) { throw 'No se encuentra Java (java.exe).' }
                return \$javaExe
              }

              function Ensure-JMeter {
                New-Item -ItemType Directory -Force -Path "${env.JMETER_DIR}" | Out-Null
                if (!(Test-Path "${env.JMETER_BAT}")) {
                  Write-Host "JMeter no encontrado. Descargando ${env.JMETER_VER}..."
                  \$zipPath = Join-Path "${env.JMETER_DIR}" "${env.JMETER_ZIP}"
                  Invoke-WebRequest -Uri "${env.JMETER_URL}" -OutFile \$zipPath -UseBasicParsing
                  Expand-Archive -Path \$zipPath -DestinationPath "${env.JMETER_DIR}" -Force
                }
                if (!(Test-Path "${env.JMETER_BAT}")) { throw "No se pudo preparar JMeter en ${env.JMETER_BAT}" }
                return "${env.JMETER_BAT}"
              }

              # Asegura Java para JMeter
              \$javaExe = Resolve-JavaExe
              \$javaHome = Split-Path (Split-Path \$javaExe -Parent) -Parent
              \$env:JAVA_HOME = \$javaHome
              \$env:PATH = "\$javaHome\\bin;\$env:PATH"

              \$jmeterExe = Ensure-JMeter

              # Requisito: 5 hilos; 40 llamadas a suma y 40 a resta => 5 hilos * 8 loops = 40 por sampler
              Copy-Item "${env.JMETER_JMX_BASE}" "${env.JMETER_JMX}" -Force
              (Get-Content "${env.JMETER_JMX}" -Raw) `
                -replace '<stringProp name="ThreadGroup.num_threads">\\d+</stringProp>','<stringProp name="ThreadGroup.num_threads">5</stringProp>' `
                -replace '<stringProp name="LoopController.loops">\\d+</stringProp>','<stringProp name="LoopController.loops">8</stringProp>' `
                | Set-Content "${env.JMETER_JMX}" -Encoding UTF8

              \$flProc = Start-Process -FilePath "cmd.exe" -ArgumentList @(
                "/c",
                "${env.PY} -m flask --app app/api.py run --host ${env.FLASK_HOST} --port ${env.FLASK_PORT}"
              ) -PassThru -WindowStyle Hidden
              \$flProc.Id | Out-File -Encoding ascii "${env.FLASK_PID_FILE}"

              Wait-Port ${env.FLASK_PORT} 30

              & \$jmeterExe -n -t "${env.JMETER_JMX}" -l "${env.JMETER_JTL}"
            """
          }
        }
      }
      post {
        always {
          script {
            archiveArtifacts allowEmptyArchive: true, artifacts: "${env.JMETER_JTL},${env.JMETER_JMX}"
            if (fileExists(env.JMETER_JTL)) {
              perfReport sourceDataFiles: "${env.JMETER_JTL}"
            } else {
              echo "perfReport: no hay ${env.JMETER_JTL} (JMeter no generó resultados)."
            }
          }
        }
      }
    }

    stage('Coverage') {
      steps {
        script {
          recordCoverage tools: [[parser: 'COBERTURA', pattern: "${env.COVERAGE_XML}"]]

          def rates = powershell(returnStdout: true, script: """
            if (Test-Path "${env.COVERAGE_XML}") {
              [xml]\$x = Get-Content "${env.COVERAGE_XML}"
              \$line = [double]\$x.coverage.'line-rate' * 100
              \$branch = [double]\$x.coverage.'branch-rate' * 100
              "{0:N2};{1:N2}" -f \$line, \$branch
            } else { "0;0" }
          """).trim()

          def parts = rates.split(';')
          double linePct = parts[0].replace(',', '.') as double
          double branchPct = parts[1].replace(',', '.') as double

          echo "Coverage => Lines: ${linePct}%, Branches: ${branchPct}%"

          boolean fail = (linePct < 85.0) || (branchPct < 80.0)
          boolean unstable = (!fail) && (
            (linePct >= 85.0 && linePct <= 95.0) ||
            (branchPct >= 80.0 && branchPct <= 90.0)
          )

          if (fail) {
            catchError(stageResult: 'FAILURE', buildResult: 'FAILURE') {
              error "Coverage por debajo del mínimo => UNHEALTHY (rojo), pero el pipeline continúa."
            }
          } else if (unstable) {
            catchError(stageResult: 'UNSTABLE', buildResult: 'UNSTABLE') {
              error "Coverage en rango UNSTABLE => amarillo, pero el pipeline continúa."
            }
          } else {
            echo "Coverage OK (líneas >95 y ramas >90)."
          }
        }
      }
    }
  }
}
