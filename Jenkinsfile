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
    BANDIT_LOG  = 'bandit.log'   // formateado tipo PEP8 para Warnings-NG

    UNIT_JUNIT = 'result-unit.xml'
    REST_JUNIT = 'result-rest.xml'

    COVERAGE_XML = 'coverage.xml'

    JMETER_JMX_BASE = 'test\\jmeter\\flask.jmx'
    JMETER_JMX = 'flask_cp12.jmx'
    JMETER_JTL = 'jmeter.jtl'

    // Flags para decidir resultado final SIN cortar el pipeline
    QG_FAIL = '0'
    QG_UNSTABLE = '0'
  }

  stages {

    stage('Checkout') {
      steps { checkout scm }
    }

    stage('Unit') {
      steps {
        powershell """
          \$ErrorActionPreference = 'Stop'
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

          // Publica en Warnings-NG (esto te funciona)
          recordIssues tools: [flake8(pattern: env.FLAKE8_REPORT)]
          archiveArtifacts allowEmptyArchive: true, artifacts: "${env.FLAKE8_REPORT}"

          // Baremos: >=10 rojo, 8-9 amarillo, <8 ok
          if (findings >= 10) {
            env.QG_FAIL = '1'
            catchError(stageResult: 'FAILURE', buildResult: 'SUCCESS') {
              error "Flake8: ${findings} findings (>=10) => stage FAILURE, build deferred to final gate."
            }
          } else if (findings >= 8) {
            if (env.QG_FAIL != '1') { env.QG_UNSTABLE = '1' }
            catchError(stageResult: 'UNSTABLE', buildResult: 'SUCCESS') {
              error "Flake8: ${findings} findings (>=8) => stage UNSTABLE, build deferred to final gate."
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
          // 1) Bandit a JSON (no rompe)
          powershell(returnStatus: true, script: """
            \$ErrorActionPreference = 'Continue'
            ${env.PY} -m bandit -r app -f json -o ${env.BANDIT_JSON} 2>\$null
            exit 0
          """)

          // 2) JSON -> bandit.log en formato PEP8: file:line:col: CODE message
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

          // 3) Cuenta findings
          def countStr = powershell(returnStdout: true, script: """
            if (Test-Path "${env.BANDIT_JSON}") {
              (Get-Content "${env.BANDIT_JSON}" -Raw | ConvertFrom-Json).results.Count
            } else { 0 }
          """).trim()
          int findings = countStr.isInteger() ? countStr.toInteger() : 0

          echo "Bandit findings: ${findings}"

          // 4) Publica en Warnings-NG usando parser PEP8 (porque tu Jenkins no soporta parser custom)
          recordIssues tools: [pep8(pattern: env.BANDIT_LOG)]

          archiveArtifacts allowEmptyArchive: true, artifacts: "${env.BANDIT_JSON},${env.BANDIT_LOG}"

          // 5) Baremos Bandit: >=4 rojo, 2-3 amarillo, <2 ok
          if (findings >= 4) {
            env.QG_FAIL = '1'
            catchError(stageResult: 'FAILURE', buildResult: 'SUCCESS') {
              error "Bandit: ${findings} findings (>=4) => stage FAILURE, build deferred to final gate."
            }
          } else if (findings >= 2) {
            if (env.QG_FAIL != '1') { env.QG_UNSTABLE = '1' }
            catchError(stageResult: 'UNSTABLE', buildResult: 'SUCCESS') {
              error "Bandit: ${findings} findings (>=2) => stage UNSTABLE, build deferred to final gate."
            }
          } else {
            echo "Bandit: ${findings} findings (<2) => OK."
          }
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
            if (\$env:JMETER_HOME) {
              \$p = Join-Path \$env:JMETER_HOME 'bin\\jmeter.bat'
              if (Test-Path \$p) { return \$p }
            }
            try {
              \$lines = & where.exe jmeter.bat 2>\$null
              if (\$LASTEXITCODE -eq 0 -and \$lines) { return \$lines[0] }
            } catch { }
            throw 'No se encuentra JMeter (jmeter.bat). Pon JMETER_HOME o jmeter en PATH.'
          }

          \$jmeterExe = Resolve-JMeterExe

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
          recordCoverage tools: [[parser: 'COBERTURA', pattern: "${env.COVERAGE_XML}"]], sourceFileResolver: 'NEVER_STORE'

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
          boolean unstableRange = (!fail) && ((linePct >= 85.0 && linePct <= 95.0) || (branchPct >= 80.0 && branchPct <= 90.0))

          if (fail) {
            env.QG_FAIL = '1'
            catchError(stageResult: 'FAILURE', buildResult: 'SUCCESS') {
              error "Coverage below minimum => stage FAILURE, build deferred to final gate."
            }
          } else if (unstableRange) {
            if (env.QG_FAIL != '1') { env.QG_UNSTABLE = '1' }
            catchError(stageResult: 'UNSTABLE', buildResult: 'SUCCESS') {
              error "Coverage in UNSTABLE range => stage UNSTABLE, build deferred to final gate."
            }
          } else {
            echo "Coverage OK (lines>95 and branches>90)."
          }
        }
      }
    }

    stage('Quality Gate (Final)') {
      steps {
        script {
          echo "Quality Gate flags => FAIL=${env.QG_FAIL}, UNSTABLE=${env.QG_UNSTABLE}"

          if (env.QG_FAIL == '1') {
            error "QUALITY GATE FAILED => Build FAILURE"
          }

          if (env.QG_UNSTABLE == '1') {
            unstable "QUALITY GATE UNSTABLE => Build UNSTABLE"
          } else {
            echo "QUALITY GATE PASSED => Build SUCCESS"
          }
        }
      }
    }
  }
}
