pipeline {
  agent any

  options {
    timestamps()
  }

  environment {
    PY = 'py -3.11'
    FLASK_PORT = '5000'
    WIREMOCK_PORT = '9090'
    FLASK_PID_FILE = 'flask.pid'
    WIREMOCK_PID_FILE = 'wiremock.pid'
    WIREMOCK_JAR = 'test\\wiremock\\wiremock-standalone-3.13.2.jar'
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

          # ---- Start Wiremock (background) ----
          if (!(Test-Path '${env.WIREMOCK_JAR}')) {
            throw "Wiremock jar not found at: ${env.WIREMOCK_JAR}"
          }

          \$wm = Start-Process -FilePath "java" -ArgumentList "-jar","${env.WIREMOCK_JAR}","--port","${env.WIREMOCK_PORT}" -PassThru
          \$wm.Id | Out-File -Encoding ascii ${env.WIREMOCK_PID_FILE}

          # ---- Start Flask (background) ----
          \$fl = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "${env.PY} app\\api.py" -PassThru
          \$fl.Id | Out-File -Encoding ascii ${env.FLASK_PID_FILE}

          function Wait-Port([int]\$port, [int]\$seconds) {
            \$deadline = (Get-Date).AddSeconds(\$seconds)
            while ((Get-Date) -lt \$deadline) {
              try {
                \$client = New-Object System.Net.Sockets.TcpClient
                \$iar = \$client.BeginConnect('127.0.0.1', \$port, \$null, \$null)
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

          Wait-Port ${env.WIREMOCK_PORT} 20
          Wait-Port ${env.FLASK_PORT} 20

          # ---- Run REST tests ----
          ${env.PY} -m pytest --junitxml=result-rest.xml test\\rest
        """
      }
      post {
        always {
          powershell """
            \$ErrorActionPreference = 'SilentlyContinue'

            # Stop Flask
            if (Test-Path '${env.FLASK_PID_FILE}') {
              \$pid = Get-Content '${env.FLASK_PID_FILE}'
              Stop-Process -Id \$pid -Force -ErrorAction SilentlyContinue
              Remove-Item '${env.FLASK_PID_FILE}' -Force -ErrorAction SilentlyContinue
            }

            # Stop Wiremock
            if (Test-Path '${env.WIREMOCK_PID_FILE}') {
              \$pid = Get-Content '${env.WIREMOCK_PID_FILE}'
              Stop-Process -Id \$pid -Force -ErrorAction SilentlyContinue
              Remove-Item '${env.WIREMOCK_PID_FILE}' -Force -ErrorAction SilentlyContinue
            }
          """
          junit allowEmptyResults: true, testResults: 'result-rest.xml'
          archiveArtifacts allowEmptyArchive: true, artifacts: 'result-rest.xml'
        }
      }
    }
  }
}
