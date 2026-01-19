pipeline {
  agent any

  options {
    timestamps()
  }

  environment {
    // Fuerza Python 3.11 con el py launcher (sin rutas absolutas)
    PY = 'py -3.11'

    FLASK_HOST = '127.0.0.1'
    FLASK_PORT = '5000'
    WIREMOCK_PORT = '9090'

    FLASK_PID_FILE = 'flask.pid'
    WIREMOCK_PID_FILE = 'wiremock.pid'

    // WireMock (se descarga si falta)
    WM_DIR = 'tools\\wiremock'
    WM_JAR = 'tools\\wiremock\\wiremock-standalone-3.13.2.jar'
    WM_URL = 'https://repo1.maven.org/maven2/org/wiremock/wiremock-standalone/3.13.2/wiremock-standalone-3.13.2.jar'

    // JMeter (auto-descarga si falta)
    JMETER_VERSION = '5.6.3'
    JMETER_DIR = 'tools\\jmeter'
    JMETER_ZIP = 'tools\\jmeter\\apache-jmeter.zip'
    JMETER_HOME = 'tools\\jmeter\\apache-jmeter'
    JMETER_RESULTS = 'performance\\results.jtl'
    JMETER_REPORT_DIR = 'performance\\html-report'
  }

  stages {

    stage('Checkout') {
      steps {
        checkout scm
      }
    }

    stage('Unit') {
      steps {
        powershell """
          \$ErrorActionPreference = 'Stop'

          # Ejecutamos unit una sola vez bajo coverage:
          ${env.PY} -m coverage run -m pytest --junitxml=result-unit.xml test\\unit

          # Generamos reportes de coverage (Cobertura XML)
          ${env.PY} -m coverage xml -o coverage.xml
          ${env.PY} -m coverage report -m
        """
      }
      post {
        always {
          junit allowEmptyResults: true, testResults: 'result-unit.xml'
          archiveArtifacts allowEmptyArchive: true, artifacts: 'result-unit.xml,coverage.xml'
        }
      }
    }

    stage('REST') {
      steps {
        powershell """
          \$ErrorActionPreference = 'Stop'

          # Asegura que java esté disponible:
          # Si JAVA_HOME está definido, lo preprendemos al PATH del proceso (no toca variables del sistema)
          if (\$env:JAVA_HOME -and (Test-Path (Join-Path \$env:JAVA_HOME 'bin'))) {
            \$env:PATH = (Join-Path \$env:JAVA_HOME 'bin') + ';' + \$env:PATH
          }
          if (-not (Get-Command java -ErrorAction SilentlyContinue)) {
            throw "No se encuentra Java (java.exe). Revisa JAVA_HOME o PATH del servicio Jenkins."
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
          Write-Host "WireMock PID: \$([int]\$wmProc.Id)"

          # --- Arrancar Flask (background) ---
          \$flProc = Start-Process -FilePath "cmd.exe" -ArgumentList @(
            "/c",
            "${env.PY} -m flask --app app/api.py run --host ${env.FLASK_HOST} --port ${env.FLASK_PORT}"
          ) -PassThru -WindowStyle Hidden
          \$flProc.Id | Out-File -Encoding ascii "${env.FLASK_PID_FILE}"
          Write-Host "Flask PID: \$([int]\$flProc.Id)"

          # --- Esperar servicios ---
          Wait-Port ${env.WIREMOCK_PORT} 30
          Wait-Port ${env.FLASK_PORT} 30

          # --- Ejecutar tests REST ---
          ${env.PY} -m pytest --junitxml=result-rest.xml test\\rest
        """
      }

      post {
        always {
          // Cleanup (no debe fallar aunque el stage haya fallado)
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

    stage('Static (flake8)') {
      steps {
        powershell """
          \$ErrorActionPreference = 'Stop'
          # flake8 devuelve exit code != 0 si hay findings, por eso usamos --exit-zero
          ${env.PY} -m flake8 app test --exit-zero > flake8.txt
          Get-Content flake8.txt | Select-Object -First 50
        """
        // Publica findings en Warnings-NG y aplica umbrales:
        // >=8 => UNSTABLE, >=10 => FAILED/rojo (pero el pipeline sigue)
        recordIssues(
          enabledForFailure: true,
          tools: [flake8(pattern: 'flake8.txt')],
          qualityGates: [
            [threshold: 8, type: 'TOTAL', unstable: true],
            [threshold: 10, type: 'TOTAL', failed: true]
          ]
        )
        archiveArtifacts allowEmptyArchive: true, artifacts: 'flake8.txt'
      }
    }

    stage('Security Test (bandit)') {
      steps {
        powershell """
          \$ErrorActionPreference = 'Stop'
          # Bandit en JSON para que Warnings-NG lo parsee. --exit-zero evita romper el stage.
          ${env.PY} -m bandit -r app -f json -o bandit.json --exit-zero
          (Get-Content bandit.json -Raw).Substring(0, [Math]::Min(800, (Get-Content bandit.json -Raw).Length))
        """
        // >=2 => UNSTABLE, >=4 => FAILED/rojo 
        recordIssues(
          enabledForFailure: true,
          tools: [bandit(pattern: 'bandit.json')],
          qualityGates: [
            [threshold: 2, type: 'TOTAL', unstable: true],
            [threshold: 4, type: 'TOTAL', failed: true]
          ]
        )
        archiveArtifacts allowEmptyArchive: true, artifacts: 'bandit.json'
      }
    }

    stage('Coverage (Cobertura)') {
      steps {
        cobertura(
          coberturaReportFile: 'coverage.xml',
          failNoReports: false,
          lineCoverageTargets: '85,95,100',
          conditionalCoverageTargets: '80,90,100'
        )
      }
    }

    stage('Performance (JMeter)') {
      steps {
        powershell """
          \$ErrorActionPreference = 'Stop'

          # Asegura que java esté disponible (JMeter lo necesita)
          if (\$env:JAVA_HOME -and (Test-Path (Join-Path \$env:JAVA_HOME 'bin'))) {
            \$env:PATH = (Join-Path \$env:JAVA_HOME 'bin') + ';' + \$env:PATH
          }
          if (-not (Get-Command java -ErrorAction SilentlyContinue)) {
            throw "No se encuentra Java (java.exe). Revisa JAVA_HOME o PATH del servicio Jenkins."
          }

          # --- Levantar Flask (sin WireMock) ---
          \$flProc = Start-Process -FilePath "cmd.exe" -ArgumentList @(
            "/c",
            "${env.PY} -m flask --app app/api.py run --host ${env.FLASK_HOST} --port ${env.FLASK_PORT}"
          ) -PassThru -WindowStyle Hidden
          \$flProc.Id | Out-File -Encoding ascii "${env.FLASK_PID_FILE}"
          Write-Host "Flask PID (perf): \$([int]\$flProc.Id)"

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
          Wait-Port ${env.FLASK_PORT} 30

          # --- Preparar JMeter (descarga si falta) ---
          New-Item -ItemType Directory -Force -Path "${env.JMETER_DIR}" | Out-Null

          \$jmxPath = "performance\\cp1-2.jmx"
          New-Item -ItemType Directory -Force -Path "performance" | Out-Null

          # Genera un plan: 5 hilos, 8 loops => 40 iteraciones.
          # En cada loop hace 1 request a /sum y 1 request a /sub => 40 + 40.
          \$jmx = @'
<?xml version="1.0" encoding="UTF-8"?>
<jmeterTestPlan version="1.2" properties="5.0" jmeter="5.6.3">
  <hashTree>
    <TestPlan guiclass="TestPlanGui" testclass="TestPlan" testname="CP1.2 Reto1 - Performance" enabled="true">
      <stringProp name="TestPlan.comments"></stringProp>
      <boolProp name="TestPlan.functional_mode">false</boolProp>
      <boolProp name="TestPlan.tearDown_on_shutdown">true</boolProp>
      <boolProp name="TestPlan.serialize_threadgroups">false</boolProp>
      <elementProp name="TestPlan.user_defined_variables" elementType="Arguments" guiclass="ArgumentsPanel" testclass="Arguments" enabled="true">
        <collectionProp name="Arguments.arguments"/>
      </elementProp>
      <stringProp name="TestPlan.user_define_classpath"></stringProp>
    </TestPlan>
    <hashTree>
      <ThreadGroup guiclass="ThreadGroupGui" testclass="ThreadGroup" testname="TG 5 users x 8 loops" enabled="true">
        <stringProp name="ThreadGroup.on_sample_error">continue</stringProp>
        <elementProp name="ThreadGroup.main_controller" elementType="LoopController" guiclass="LoopControlPanel" testclass="LoopController" enabled="true">
          <boolProp name="LoopController.continue_forever">false</boolProp>
          <stringProp name="LoopController.loops">8</stringProp>
        </elementProp>
        <stringProp name="ThreadGroup.num_threads">5</stringProp>
        <stringProp name="ThreadGroup.ramp_time">1</stringProp>
        <boolProp name="ThreadGroup.scheduler">false</boolProp>
        <stringProp name="ThreadGroup.duration"></stringProp>
        <stringProp name="ThreadGroup.delay"></stringProp>
      </ThreadGroup>
      <hashTree>

        <HTTPSamplerProxy guiclass="HttpTestSampleGui" testclass="HTTPSamplerProxy" testname="SUM" enabled="true">
          <elementProp name="HTTPsampler.Arguments" elementType="Arguments">
            <collectionProp name="Arguments.arguments">
              <elementProp name="a" elementType="HTTPArgument">
                <boolProp name="HTTPArgument.always_encode">false</boolProp>
                <stringProp name="Argument.value">1</stringProp>
                <stringProp name="Argument.metadata">=</stringProp>
                <stringProp name="Argument.name">a</stringProp>
              </elementProp>
              <elementProp name="b" elementType="HTTPArgument">
                <boolProp name="HTTPArgument.always_encode">false</boolProp>
                <stringProp name="Argument.value">2</stringProp>
                <stringProp name="Argument.metadata">=</stringProp>
                <stringProp name="Argument.name">b</stringProp>
              </elementProp>
            </collectionProp>
          </elementProp>
          <stringProp name="HTTPSampler.domain">${env.FLASK_HOST}</stringProp>
          <stringProp name="HTTPSampler.port">${env.FLASK_PORT}</stringProp>
          <stringProp name="HTTPSampler.protocol">http</stringProp>
          <stringProp name="HTTPSampler.path">/sum</stringProp>
          <stringProp name="HTTPSampler.method">GET</stringProp>
          <boolProp name="HTTPSampler.follow_redirects">true</boolProp>
          <boolProp name="HTTPSampler.auto_redirects">false</boolProp>
          <boolProp name="HTTPSampler.use_keepalive">true</boolProp>
          <boolProp name="HTTPSampler.DO_MULTIPART_POST">false</boolProp>
          <stringProp name="HTTPSampler.embedded_url_re"></stringProp>
        </HTTPSamplerProxy>
        <hashTree/>

        <HTTPSamplerProxy guiclass="HttpTestSampleGui" testclass="HTTPSamplerProxy" testname="SUB" enabled="true">
          <elementProp name="HTTPsampler.Arguments" elementType="Arguments">
            <collectionProp name="Arguments.arguments">
              <elementProp name="a" elementType="HTTPArgument">
                <boolProp name="HTTPArgument.always_encode">false</boolProp>
                <stringProp name="Argument.value">2</stringProp>
                <stringProp name="Argument.metadata">=</stringProp>
                <stringProp name="Argument.name">a</stringProp>
              </elementProp>
              <elementProp name="b" elementType="HTTPArgument">
                <boolProp name="HTTPArgument.always_encode">false</boolProp>
                <stringProp name="Argument.value">1</stringProp>
                <stringProp name="Argument.metadata">=</stringProp>
                <stringProp name="Argument.name">b</stringProp>
              </elementProp>
            </collectionProp>
          </elementProp>
          <stringProp name="HTTPSampler.domain">${env.FLASK_HOST}</stringProp>
          <stringProp name="HTTPSampler.port">${env.FLASK_PORT}</stringProp>
          <stringProp name="HTTPSampler.protocol">http</stringProp>
          <stringProp name="HTTPSampler.path">/sub</stringProp>
          <stringProp name="HTTPSampler.method">GET</stringProp>
          <boolProp name="HTTPSampler.follow_redirects">true</boolProp>
          <boolProp name="HTTPSampler.auto_redirects">false</boolProp>
          <boolProp name="HTTPSampler.use_keepalive">true</boolProp>
          <boolProp name="HTTPSampler.DO_MULTIPART_POST">false</boolProp>
          <stringProp name="HTTPSampler.embedded_url_re"></stringProp>
        </HTTPSamplerProxy>
        <hashTree/>

      </hashTree>
    </hashTree>
  </hashTree>
</jmeterTestPlan>
'@
          \$jmx | Out-File -Encoding UTF8 \$jmxPath

          # Descargar JMeter
          \$zip = "${env.JMETER_ZIP}"
          \$home = "${env.JMETER_HOME}"
          if (!(Test-Path \$home)) {
            Write-Host "Descargando JMeter ${env.JMETER_VERSION}..."
            \$url = "https://archive.apache.org/dist/jmeter/binaries/apache-jmeter-${env.JMETER_VERSION}.zip"
            Invoke-WebRequest -Uri \$url -OutFile \$zip -UseBasicParsing

            # Extraer
            Expand-Archive -Path \$zip -DestinationPath "${env.JMETER_DIR}" -Force

            # Normaliza carpeta a tools\\jmeter\\apache-jmeter
            \$extracted = Join-Path "${env.JMETER_DIR}" ("apache-jmeter-" + "${env.JMETER_VERSION}")
            if (Test-Path \$extracted) {
              if (Test-Path \$home) { Remove-Item \$home -Recurse -Force }
              Move-Item \$extracted \$home
            }
          }

          \$jmeterBat = Join-Path \$home "bin\\jmeter.bat"
          if (!(Test-Path \$jmeterBat)) {
            throw "No se encontró jmeter.bat en: \$jmeterBat"
          }

          # Ejecutar JMeter en modo no-GUI
          New-Item -ItemType Directory -Force -Path "${env.JMETER_REPORT_DIR}" | Out-Null
          & \$jmeterBat -n -t \$jmxPath -l "${env.JMETER_RESULTS}" -e -o "${env.JMETER_REPORT_DIR}"
        """
      }

      post {
        always {
          // Cleanup Flask
          powershell """
            \$ErrorActionPreference = 'SilentlyContinue'
            if (Test-Path "${env.FLASK_PID_FILE}") {
              \$procId = Get-Content "${env.FLASK_PID_FILE}"
              Stop-Process -Id \$procId -Force -ErrorAction SilentlyContinue
              Remove-Item "${env.FLASK_PID_FILE}" -Force -ErrorAction SilentlyContinue
            }
          """
          // Publicar resultados de performance (Performance plugin)
          perfReport sourceDataFiles: 'performance/results.jtl'
          archiveArtifacts allowEmptyArchive: true, artifacts: 'performance/**'
        }
      }
    }
  }
}
