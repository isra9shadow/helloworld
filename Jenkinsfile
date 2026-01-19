pipeline {
  agent any

  options { timestamps() }

  environment {
    BUILD_HEALTH = 'SUCCESS' // SUCCESS | UNSTABLE | FAILURE
    VENV_DIR = '.venv'
    PY = ''                  // se setea en Init Python
  }

  stages {
    stage('Get Code') {
      steps { checkout scm }
    }

    stage('Init Python (venv + deps)') {
      steps {
        // Nunca romper el pipeline por setup: queremos que el resto siga y deje evidencias.
        catchError(buildResult: 'SUCCESS', stageResult: 'FAILURE') {
          powershell '''
            $ErrorActionPreference = "Stop"

            # Localiza python (si no, falla aquí y deja el log claro)
            $py = (Get-Command python -ErrorAction SilentlyContinue)
            if (-not $py) { throw "python no está disponible en el agente Jenkins (PATH). Instala Python 3.11+ o añade a PATH." }
            python --version

            # Crea venv si no existe
            if (!(Test-Path "${env:VENV_DIR}\\Scripts\\python.exe")) {
              python -m venv ${env:VENV_DIR}
            }

            # Actualiza pip y instala tooling mínimo
            & "${env:VENV_DIR}\\Scripts\\python.exe" -m pip install --upgrade pip

            # Si tienes requirements.txt lo usa; si no, instala lo mínimo para CP1.2
            if (Test-Path "requirements.txt") {
              & "${env:VENV_DIR}\\Scripts\\python.exe" -m pip install -r requirements.txt
            } else {
              & "${env:VENV_DIR}\\Scripts\\python.exe" -m pip install pytest coverage flake8 bandit flask
            }

            # Deja un marcador para el resto de etapas (ruta al python del venv)
            "${env:VENV_DIR}\\Scripts\\python.exe" | Out-File -Encoding ascii .pycmd
          '''
        }

        script {
          env.PY = fileExists('.pycmd') ? readFile('.pycmd').trim() : 'python'
          echo "PY => ${env.PY}"
        }
      }
      post {
        always {
          archiveArtifacts artifacts: '.pycmd', allowEmptyArchive: true
        }
      }
    }

    stage('Unit') {
      steps {
        catchError(buildResult: 'SUCCESS', stageResult: 'FAILURE') {
          powershell """
            & '${env.PY}' -m pytest -q test\\unit --junitxml=result-unit.xml
            & '${env.PY}' -m coverage run --branch --source app --omit "app\\api.py,app\\__init__.py" -m pytest -q test\\unit
            & '${env.PY}' -m coverage xml -o coverage.xml
            & '${env.PY}' -m coverage report -m
          """
        }
      }
      post {
        always {
          junit testResults: 'result-unit.xml', allowEmptyResults: true
          archiveArtifacts artifacts: 'result-unit.xml,coverage.xml', fingerprint: true, allowEmptyArchive: true
        }
      }
    }

    stage('REST') {
      steps {
        catchError(buildResult: 'SUCCESS', stageResult: 'FAILURE') {
          powershell """
            & '${env.PY}' -m pytest -q test\\rest --junitxml=result-rest.xml
          """
        }
      }
      post {
        always {
          junit testResults: 'result-rest.xml', allowEmptyResults: true
          archiveArtifacts artifacts: 'result-rest.xml', fingerprint: true, allowEmptyArchive: true
        }
      }
    }

    stage('Static (Flake8)') {
      steps {
        // 1) genera log siempre 2) publica warnings 3) aplica baremo sin cortar pipeline
        catchError(buildResult: 'SUCCESS', stageResult: 'FAILURE') {
          powershell """
            & '${env.PY}' -m flake8 app test --count --statistics --exit-zero | Tee-Object -FilePath flake8.log
            \$countLine = (Get-Content flake8.log | Select-Object -Last 1)
            if (-not \$countLine) { \$countLine = '0' }
            \$count = [int]\$countLine
            "FLAKE8_COUNT=\$count" | Out-File -FilePath flake8.count -Encoding ascii
            Write-Host "Flake8 findings: \$count"
          """
        }

        recordIssues tools: [flake8(pattern: 'flake8.log')]
        archiveArtifacts artifacts: 'flake8.log,flake8.count', fingerprint: true, allowEmptyArchive: true

        script {
          def count = fileExists('flake8.count') ? (readFile('flake8.count').trim().split('=')[1] as int) : 9999
          def stageRes = 'SUCCESS'
          def msg = "Flake8: ${count} findings => OK."

          if (count >= 10) {
            stageRes = 'FAILURE'
            msg = "Flake8: ${count} findings (>=10) => UNHEALTHY (rojo), pero el pipeline continúa."
            env.BUILD_HEALTH = worst(env.BUILD_HEALTH, 'FAILURE')
          } else if (count >= 8) {
            stageRes = 'UNSTABLE'
            msg = "Flake8: ${count} findings (>=8) => UNSTABLE (amarillo), pero el pipeline continúa."
            env.BUILD_HEALTH = worst(env.BUILD_HEALTH, 'UNSTABLE')
          }

          catchError(buildResult: 'SUCCESS', stageResult: stageRes) {
            if (stageRes != 'SUCCESS') { error(msg) } else { echo(msg) }
          }
        }
      }
    }

    stage('Security Test (Bandit)') {
      steps {
        catchError(buildResult: 'SUCCESS', stageResult: 'FAILURE') {
          powershell """
            & '${env.PY}' -m bandit -r app -f txt -o bandit.log ; \$LASTEXITCODE = 0
            & '${env.PY}' -m bandit -r app -f json -o bandit.json ; \$LASTEXITCODE = 0

            if (!(Test-Path bandit.json)) { '{}' | Out-File bandit.json -Encoding utf8 }

            \$raw = Get-Content bandit.json -Raw
            try { \$json = \$raw | ConvertFrom-Json } catch { \$json = \$null }
            \$count = 0
            if (\$json -and \$json.results) { \$count = \$json.results.Count }
            "BANDIT_COUNT=\$count" | Out-File -FilePath bandit.count -Encoding ascii
            Write-Host "Bandit findings: \$count"
          """
        }

        // Parser bandit (Warnings-NG)
        recordIssues tools: [bandit(pattern: 'bandit.log')]
        archiveArtifacts artifacts: 'bandit.log,bandit.json,bandit.count', fingerprint: true, allowEmptyArchive: true

        script {
          def count = fileExists('bandit.count') ? (readFile('bandit.count').trim().split('=')[1] as int) : 9999
          def stageRes = 'SUCCESS'
          def msg = "Bandit: ${count} findings => OK."

          if (count >= 4) {
            stageRes = 'FAILURE'
            msg = "Bandit: ${count} findings (>=4) => UNHEALTHY (rojo), pero el pipeline continúa."
            env.BUILD_HEALTH = worst(env.BUILD_HEALTH, 'FAILURE')
          } else if (count >= 2) {
            stageRes = 'UNSTABLE'
            msg = "Bandit: ${count} findings (>=2) => UNSTABLE (amarillo), pero el pipeline continúa."
            env.BUILD_HEALTH = worst(env.BUILD_HEALTH, 'UNSTABLE')
          }

          catchError(buildResult: 'SUCCESS', stageResult: stageRes) {
            if (stageRes != 'SUCCESS') { error(msg) } else { echo(msg) }
          }
        }
      }
    }

    stage('Performance (JMeter)') {
      steps {
        catchError(buildResult: 'SUCCESS', stageResult: 'FAILURE') {
          powershell """
            # Arranca Flask dentro de la stage (mejor nota)
            \$flask = Start-Process -FilePath '${env.PY}' -ArgumentList '-m','flask','run','--host=127.0.0.1','--port=5000' -PassThru -WindowStyle Hidden
            Start-Sleep -Seconds 2
            try {
              jmeter -n -t flask_cp12.jmx -l jmeter.jtl
            } finally {
              if (\$flask -and -not \$flask.HasExited) { Stop-Process -Id \$flask.Id -Force }
            }
          """
        }
      }
      post {
        always {
          archiveArtifacts artifacts: 'jmeter.jtl', fingerprint: true, allowEmptyArchive: true
          perfReport sourceDataFiles: 'jmeter.jtl'
        }
      }
    }

    stage('Coverage') {
      steps {
        // Publica coverage siempre (si existe), y aplica baremo
        catchError(buildResult: 'SUCCESS', stageResult: 'FAILURE') {
          powershell """
            if (!(Test-Path coverage.xml)) {
              # por si Unit falló y no generó coverage, lo intentamos aquí para no perder evidencia
              & '${env.PY}' -m coverage run --branch --source app --omit "app\\api.py,app\\__init__.py" -m pytest -q test\\unit
              & '${env.PY}' -m coverage xml -o coverage.xml
            }
          """
        }

        recordCoverage tools: [[parser: 'COBERTURA', pattern: 'coverage.xml']]
        archiveArtifacts artifacts: 'coverage.xml', fingerprint: true, allowEmptyArchive: true

        script {
          catchError(buildResult: 'SUCCESS', stageResult: 'FAILURE') {
            powershell """
              [xml]\$x = Get-Content coverage.xml
              \$line = [double]\$x.coverage.'line-rate' * 100.0
              \$branch = [double]\$x.coverage.'branch-rate' * 100.0
              "LINE_RATE=\$line" | Out-File coverage.line -Encoding ascii
              "BRANCH_RATE=\$branch" | Out-File coverage.branch -Encoding ascii
              Write-Host ("Coverage => Lines: {0:N2}%, Branches: {1:N2}%" -f \$line, \$branch)
            """
          }

          def line = fileExists('coverage.line') ? (readFile('coverage.line').trim().split('=')[1] as double) : 0.0
          def branch = fileExists('coverage.branch') ? (readFile('coverage.branch').trim().split('=')[1] as double) : 0.0

          def stageRes = 'SUCCESS'
          if (line < 85.0 || branch < 80.0) {
            stageRes = 'FAILURE'
            env.BUILD_HEALTH = worst(env.BUILD_HEALTH, 'FAILURE')
          } else if ((line >= 85.0 && line <= 95.0) || (branch >= 80.0 && branch <= 90.0)) {
            stageRes = 'UNSTABLE'
            env.BUILD_HEALTH = worst(env.BUILD_HEALTH, 'UNSTABLE')
          }

          def msg = "Coverage => Lines: ${String.format('%.2f', line)}%, Branches: ${String.format('%.2f', branch)}%"
          catchError(buildResult: 'SUCCESS', stageResult: stageRes) {
            if (stageRes != 'SUCCESS') { error("Coverage fuera de baremo => ${stageRes}. ${msg}") } else { echo(msg) }
          }
        }
      }
    }
  }

  post {
    always {
      script {
        currentBuild.result = env.BUILD_HEALTH
        echo "Build health final => ${currentBuild.result}"
      }
    }
  }
}

def worst(String a, String b) {
  def order = ['SUCCESS': 0, 'UNSTABLE': 1, 'FAILURE': 2]
  return (order[b] > order[a]) ? b : a
}
