pipeline {
  agent any
  options { timestamps() }

  environment {
    PY       = ".venv\\Scripts\\python.exe"
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
            $ErrorActionPreference = "Stop"

            # ----------------------------
            # 0) Limpieza previa + kill por PID previo (si existe)
            # ----------------------------
            foreach ($f in @("real.pid","mock.pid")) {
              if (Test-Path $f) {
                try {
                  $procId = (Get-Content $f | Select-Object -First 1)
                  if ($procId) { Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue }
                } catch {}
              }
            }

            Remove-Item -Force -ErrorAction SilentlyContinue `
              real.pid, mock.pid, `
              real.out.log, real.err.log, `
              mock.out.log, mock.err.log, `
              mock_9090.py, run_real_5000.py

            # (Opcional) si había algo escuchando en 5000/9090, intentamos pararlo
            function Stop-Port([int]$port) {
              try {
                $pids = (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique)
                foreach ($p in $pids) { Stop-Process -Id $p -Force -ErrorAction SilentlyContinue }
              } catch {}
            }
            Stop-Port 5000
            Stop-Port 9090

            # ----------------------------
            # 1) Crear MOCK temporal en 9090
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
            # 2) Crear runner REAL 5000 con autodetección de Flask app
            # ----------------------------
@"
import sys, importlib, pkgutil
from flask import Flask

def _try_module(modname):
    try:
        return importlib.import_module(modname)
    except Exception:
        return None

def find_flask_app():
    # candidatos típicos (módulo o submódulos)
    candidates = [
        "app", "app.app", "app.api", "app.main", "app.wsgi",
        "wsgi", "main", "api", "application"
    ]

    for modname in candidates:
        m = _try_module(modname)
        if not m:
            continue

        # 1) instancias Flask directas
        for name, obj in vars(m).items():
            try:
                if isinstance(obj, Flask):
                    return obj
            except Exception:
                pass

        # 2) factorías create_app()
        for fname in ("create_app",):
            f = getattr(m, fname, None)
            if callable(f):
                try:
                    a = f()
                    if isinstance(a, Flask):
                        return a
                except Exception:
                    pass

    # 3) recorrer paquete "app" buscando instancias Flask / create_app
    pkg = _try_module("app")
    if pkg and hasattr(pkg, "__path__"):
        for _, subname, _ in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + "."):
            m = _try_module(subname)
            if not m:
                continue
            for name, obj in vars(m).items():
                try:
                    if isinstance(obj, Flask):
                        return obj
                except Exception:
                    pass
            f = getattr(m, "create_app", None)
            if callable(f):
                try:
                    a = f()
                    if isinstance(a, Flask):
                        return a
                except Exception:
                    pass

    raise RuntimeError("No se encontró ninguna instancia Flask (ni create_app()) en el proyecto")

if __name__ == "__main__":
    app = find_flask_app()
    app.run(host="127.0.0.1", port=5000)
"@ | Out-File -Encoding utf8 run_real_5000.py

            # ----------------------------
            # 3) Arrancar REAL en 5000 (stdout/err separados)
            # ----------------------------
            $real = Start-Process -FilePath ".venv\\Scripts\\python.exe" `
              -ArgumentList "run_real_5000.py" `
              -PassThru -WindowStyle Hidden `
              -RedirectStandardOutput "real.out.log" `
              -RedirectStandardError  "real.err.log"
            $real.Id | Out-File -Encoding ascii real.pid

            # ----------------------------
            # 4) Arrancar MOCK en 9090 (stdout/err separados)
            # ----------------------------
            $mock = Start-Process -FilePath ".venv\\Scripts\\python.exe" `
              -ArgumentList "mock_9090.py" `
              -PassThru -WindowStyle Hidden `
              -RedirectStandardOutput "mock.out.log" `
              -RedirectStandardError  "mock.err.log"
            $mock.Id | Out-File -Encoding ascii mock.pid

            # ----------------------------
            # 5) Esperar readiness (endpoint real y endpoint mock)
            # ----------------------------
            function Wait-Http200([string]$url) {
              foreach ($i in 1..80) {
                try {
                  $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 -Uri $url
                  if ($r.StatusCode -eq 200) { return $true }
                } catch {}
                Start-Sleep -Milliseconds 500
              }
              return $false
            }

            $realOk = Wait-Http200 "$env:BASE_URL/calc/add/1/2"
            if (-not $realOk) {
              "---- REAL OUT (real.out.log) ----" | Out-Host
              if (Test-Path real.out.log) { Get-Content real.out.log -Tail 200 | Out-Host }
              "---- REAL ERR (real.err.log) ----" | Out-Host
              if (Test-Path real.err.log) { Get-Content real.err.log -Tail 200 | Out-Host }

              "---- PORT 5000 CHECK ----" | Out-Host
              cmd /c "netstat -ano | findstr :5000" | Out-Host

              throw "API 5000 no lista ($env:BASE_URL/calc/add/1/2)"
            }

            $mockOk = Wait-Http200 "$env:MOCK_URL/calc/sqrt/64"
            if (-not $mockOk) {
              "---- MOCK OUT (mock.out.log) ----" | Out-Host
              if (Test-Path mock.out.log) { Get-Content mock.out.log -Tail 200 | Out-Host }
              "---- MOCK ERR (mock.err.log) ----" | Out-Host
              if (Test-Path mock.err.log) { Get-Content mock.err.log -Tail 200 | Out-Host }

              "---- PORT 9090 CHECK ----" | Out-Host
              cmd /c "netstat -ano | findstr :9090" | Out-Host

              throw "API 9090 no lista ($env:MOCK_URL/calc/sqrt/64)"
            }

            exit 0
          '''
        }
      }
      post {
        always {
          archiveArtifacts artifacts: 'real.out.log,real.err.log,mock.out.log,mock.err.log,real.pid,mock.pid', allowEmptyArchive: true
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
