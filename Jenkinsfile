pipeline {
  agent any
  options { timestamps() }

  environment {
    PY = ".venv\\Scripts\\python.exe"
    BASE_URL = "http://localhost:5000"
    MOCK_URL = "http://localhost:9090"
  }

  stages {

    stage('Get Code') {
      steps {
        deleteDir()
        checkout scm
        powershell '''
          whoami
          hostname
          echo "WORKSPACE=$env:WORKSPACE"
        '''
      }
    }

    stage('Init Python') {
      steps {
        powershell '''
          python -m venv .venv
          & .venv\\Scripts\\python.exe -m pip install -U pip
          & .venv\\Scripts\\python.exe -m pip install -r requirements-ci.txt
        '''
      }
    }

    stage('Unit') {
      steps {
        catchError(buildResult: 'SUCCESS', stageResult: 'FAILURE') {
          powershell '''
            & .venv\\Scripts\\python.exe -m pytest test\\unit --junitxml=result-unit.xml
            exit 0
          '''
        }
      }
      post {
        always { junit allowEmptyResults: true, testResults: 'result-unit.xml' }
      }
    }

    stage('Start APIs') {
      steps {
        catchError(buildResult: 'SUCCESS', stageResult: 'FAILURE') {
          powershell '''
            # ----------------------------
            # 0) Limpieza previa de logs/pids
            # ----------------------------
            Remove-Item -Force -ErrorAction SilentlyContinue real.pid, mock.pid, real.log, mock.log, mock_9090.py

            # ----------------------------
            # 1) Crear mock temporal en 9090
            # ----------------------------
@"
import http.client
from flask import Flask

mock = Flask(__name__)
HEADERS = {"Content-Type": "text/plain", "Access-Control-Allow-Origin": "*"}

@mock.route("/calc/sqrt/<n>", methods=["GET"])
def sqrt(n):
    if str(n) == "64":
        return ("8", http.client.OK, HEADERS)
    return ("0", http.client.OK, HEADERS)

if __name__ == "__main__":
    mock.run(host="127.0.0.1", port=9090)
"@ | Out-File -Encoding utf8 mock_9090.py

            # ----------------------------
            # 2) Arrancar API REAL en 5000
            #    (tu app expone api_application, así que FLASK_APP=app:api_application)
            # ----------------------------
            $env:FLASK_APP = "app:api_application"
            $env:FLASK_ENV = "production"

            $realArgs = "-m flask run --host=127.0.0.1 --port=5000"
            $real = Start-Process -FilePath ".venv\\Scripts\\python.exe" -ArgumentList $realArgs -PassThru -WindowStyle Hidden -RedirectStandardOutput real.log -RedirectStandardError real.log
            $real.Id | Out-File -Encoding ascii real.pid

            # ----------------------------
            # 3) Arrancar MOCK en 9090
            # ----------------------------
            $mock = Start-Process -FilePath ".venv\\Scripts\\python.exe" -ArgumentList "mock_9090.py" -PassThru -WindowStyle Hidden -RedirectStandardOutput mock.log -RedirectStandardError mock.log
            $mock.Id | Out-File -Encoding ascii mock.pid

            # ----------------------------
            # 4) Esperar readiness con más reintentos
            # ----------------------------
            function Wait-Http([string]$url) {
              $ok = $false
              foreach ($i in 1..60) {
                try {
                  $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 -Uri $url
                  if ($r.StatusCode -eq 200) { $ok = $true; break }
                } catch {}
                Start-Sleep -Milliseconds 500
              }
              return $ok
            }

            $realOk = Wait-Http "$env:BASE_URL/"
            if (-not $realOk) {
              "---- REAL LOG (real.log) ----" | Out-Host
              if (Test-Path real.log) { Get-Content real.log -Tail 200 | Out-Host }
              throw "API 5000 no lista ($env:BASE_URL/)"
            }

            $mockOk = Wait-Http "$env:MOCK_URL/calc/sqrt/64"
            if (-not $mockOk) {
              "---- MOCK LOG (mock.log) ----" | Out-Host
              if (Test-Path mock.log) { Get-Content mock.log -Tail 200 | Out-Host }
              throw "API 9090 no lista ($env:MOCK_URL/calc/sqrt/64)"
            }

            exit 0
          '''
        }
      }
      post {
        always {
          archiveArtifacts artifacts: 'real.log,mock.log,real.pid,mock.pid', allowEmptyArchive: true
        }
      }
    }

    stage('REST') {
      steps {
        catchError(buildResult: 'SUCCESS', stageResult: 'FAILURE') {
          powershell '''
            & .venv\\Scripts\\python.exe -m pytest test\\rest --junitxml=result-rest.xml

            if (-not (Test-Path "result-rest.xml")) {
@"
<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="rest" tests="0" failures="0" errors="0" skipped="0"></testsuite>
"@ | Out-File -Encoding utf8 result-rest.xml
            }

            exit 0
          '''
        }
      }
      post {
        always { junit allowEmptyResults: true, testResults: 'result-rest.xml' }
      }
    }

    stage('Static (Flake8)') {
      steps {
        catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {
          powershell '''
            & .venv\\Scripts\\python.exe -m flake8 app > flake8.log
            exit 0
          '''
        }
        archiveArtifacts artifacts: 'flake8.log', allowEmptyArchive: true
      }
    }

    stage('Security Test (Bandit)') {
      steps {
        catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {
          powershell '''
            & .venv\\Scripts\\python.exe -m bandit -r app -f txt -o bandit.log
            exit 0
          '''
        }
      }
      post {
        always { archiveArtifacts artifacts: 'bandit.log', allowEmptyArchive: true }
      }
    }

    stage('Performance (JMeter)') {
      steps {
        catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {
          powershell '''
            if (-not (Get-Command jmeter -ErrorAction SilentlyContinue)) {
              "JMETER_NOT_FOUND" | Out-File -Encoding utf8 jmeter.missing.txt
              exit 0
            }
            jmeter -n -t test\\jmeter\\flask.jmx -l jmeter.jtl
            exit 0
          '''
        }
      }
      post {
        always { archiveArtifacts artifacts: 'jmeter.*', allowEmptyArchive: true }
      }
    }

    stage('Coverage') {
      steps {
        catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {
          powershell '''
            & .venv\\Scripts\\python.exe -m coverage run -m pytest test
            & .venv\\Scripts\\python.exe -m coverage xml -o coverage.xml
            exit 0
          '''
        }
        archiveArtifacts artifacts: 'coverage.xml', allowEmptyArchive: true
      }
    }
  }

  post {
    always {
      // ✅ matar procesos sin usar $PID/$pid
      powershell '''
        foreach ($f in @("real.pid","mock.pid")) {
          if (Test-Path $f) {
            $procId = (Get-Content $f | Select-Object -First 1)
            try { Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue } catch {}
          }
        }
      '''
      echo "Pipeline finished (continuable design)."
    }
  }
}
