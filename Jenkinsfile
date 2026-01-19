pipeline {
  agent any

  options {
    timestamps()
    skipDefaultCheckout(true)
  }

  environment {
    PY = ".venv\\Scripts\\python.exe"
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
          '''
        }
      }
      post {
        always {
          junit allowEmptyResults: true, testResults: 'result-unit.xml'
        }
      }
    }

    stage('REST') {
      steps {
        catchError(buildResult: 'SUCCESS', stageResult: 'FAILURE') {
          powershell '''
            $ErrorActionPreference = "Stop"

            # --- CI servers (5000 + 9090) ---
            New-Item -ItemType Directory -Force -Path ".ci" | Out-Null

            $server = @"
from flask import Flask, Response
import math, os

app = Flask(__name__)

@app.get("/health")
def health():
    return "ok"

@app.get("/calc/add/<a>/<b>")
def add(a,b):
    try:
        r = float(a) + float(b)
    except:
        return Response("bad request", status=400)
    return str(int(r)) if r.is_integer() else str(r)

@app.get("/calc/sub/<a>/<b>")
def sub(a,b):
    try:
        r = float(a) - float(b)
    except:
        return Response("bad request", status=400)
    return str(int(r)) if r.is_integer() else str(r)

@app.get("/calc/sqrt/<n>")
def sqrt(n):
    try:
        r = math.sqrt(float(n))
    except:
        return Response("bad request", status=400)
    return str(int(r)) if r.is_integer() else str(r)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="127.0.0.1", port=port, debug=False)
"@

            Set-Content -Path ".ci\\rest_server.py" -Value $server -Encoding UTF8

            # matar procesos que estén escuchando en 5000/9090 (si quedó algo de runs anteriores)
            foreach($p in @(5000,9090)) {
              try {
                $conns = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue
                foreach($c in $conns) {
                  Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
                }
              } catch {}
            }

            $p5000 = $null
            $p9090 = $null
            $exitCode = 0

            function Wait-Url($url) {
              for($i=0; $i -lt 30; $i++){
                try {
                  Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 1 | Out-Null
                  return $true
                } catch {
                  Start-Sleep 1
                }
              }
              return $false
            }

            try {
              # 5000
              Remove-Item Env:PORT -ErrorAction SilentlyContinue
              $p5000 = Start-Process -FilePath $env:PY -ArgumentList ".ci\\rest_server.py" -PassThru -WindowStyle Hidden -WorkingDirectory $env:WORKSPACE

              # 9090
              $env:PORT = "9090"
              $p9090 = Start-Process -FilePath $env:PY -ArgumentList ".ci\\rest_server.py" -PassThru -WindowStyle Hidden -WorkingDirectory $env:WORKSPACE
              Remove-Item Env:PORT -ErrorAction SilentlyContinue

              if(-not (Wait-Url "http://localhost:5000/health")) { throw "API 5000 no lista" }
              if(-not (Wait-Url "http://localhost:9090/health")) { throw "MOCK 9090 no lista" }

              & .venv\\Scripts\\python.exe -m pytest test\\rest --junitxml=result-rest.xml
              $exitCode = $LASTEXITCODE
            }
            finally {
              if($p5000) { Stop-Process -Id $p5000.Id -Force -ErrorAction SilentlyContinue }
              if($p9090) { Stop-Process -Id $p9090.Id -Force -ErrorAction SilentlyContinue }
            }

            exit $exitCode
          '''
        }
      }
      post {
        always {
          junit allowEmptyResults: true, testResults: 'result-rest.xml'
        }
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
        recordIssues tools: [flake8(pattern: 'flake8.log')]
      }
    }

    stage('Security Test (Bandit)') {
      steps {
        catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {
          powershell '''
            & .venv\\Scripts\\python.exe -m bandit -r app -f sarif -o bandit.sarif -q
            exit 0
          '''
        }
        // IMPORTANTE: tu Jenkins NO tiene bandit(), pero SÍ sarif()
        recordIssues tools: [sarif(pattern: 'bandit.sarif')]
      }
    }

    stage('Performance (JMeter)') {
      steps {
        catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {
          powershell '''
            jmeter -n -t test\\jmeter\\flask.jmx -l jmeter.jtl
          '''
        }
      }
      post {
        always {
          archiveArtifacts artifacts: 'jmeter.jtl', allowEmptyArchive: true
          perfReport sourceDataFiles: 'jmeter.jtl'
        }
      }
    }

    stage('Coverage') {
      steps {
        catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {
          powershell '''
            & .venv\\Scripts\\python.exe -m coverage run -m pytest test
            & .venv\\Scripts\\python.exe -m coverage xml
          '''
        }
        recordCoverage tools: [[parser: 'COBERTURA', pattern: 'coverage.xml']]
      }
    }

  }
}
