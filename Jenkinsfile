pipeline {
  agent any

  options {
    timestamps()
  }

  environment {
    // Para acumular el peor estado y aplicarlo al final
    BUILD_HEALTH = 'SUCCESS'  // SUCCESS | UNSTABLE | FAILURE
  }

  stages {
    stage('Get Code') {
      steps {
        checkout scm
      }
    }

    stage('Unit') {
      steps {
        // En CP1.2 no se aplica baremo a Unit: que siempre quede verde. :contentReference[oaicite:11]{index=11}
        catchError(buildResult: 'SUCCESS', stageResult: 'SUCCESS') {
          powershell '''
            pytest -q test\\unit --junitxml=result-unit.xml
            coverage run --branch --source app --omit "app\\api.py,app\\__init__.py" -m pytest -q test\\unit
            coverage xml -o coverage.xml
            coverage report -m
          '''
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
        // Igual que CP1.1, y sin baremo de “salud” (verde) :contentReference[oaicite:12]{index=12}
        catchError(buildResult: 'SUCCESS', stageResult: 'SUCCESS') {
          powershell '''
            pytest -q test\\rest --junitxml=result-rest.xml
          '''
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
        powershell '''
          # Genera log con count al final (última línea numérica)
          flake8 app test --count --statistics --exit-zero | Tee-Object -FilePath flake8.log
          $countLine = (Get-Content flake8.log | Select-Object -Last 1)
          $count = [int]$countLine
          "FLAKE8_COUNT=$count" | Out-File -FilePath flake8.count -Encoding ascii
          Write-Host "Flake8 findings: $count"
        '''

        // Publica Warnings-NG (Flake8)
        recordIssues tools: [flake8(pattern: 'flake8.log')]

        archiveArtifacts artifacts: 'flake8.log,flake8.count', fingerprint: true, allowEmptyArchive: true

        script {
          def count = readFile('flake8.count').trim().split('=')[1] as int
          def stageRes = 'SUCCESS'
          def msg = "Flake8: ${count} findings => OK."

          if (count >= 10) {
            stageRes = 'FAILURE'  // rojo
            msg = "Flake8: ${count} findings (>=10) => UNHEALTHY (rojo), pero el pipeline continúa."
            env.BUILD_HEALTH = worst(env.BUILD_HEALTH, 'FAILURE')
          } else if (count >= 8) {
            stageRes = 'UNSTABLE' // amarillo
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
        powershell '''
          # Siempre genera salida (txt + json)
          bandit -r app -f txt -o bandit.log || $true
          bandit -r app -f json -o bandit.json || $true

          $json = Get-Content bandit.json -Raw | ConvertFrom-Json
          $count = $json.results.Count
          "BANDIT_COUNT=$count" | Out-File -FilePath bandit.count -Encoding ascii
          Write-Host "Bandit findings: $count"
        '''

        // Publica Warnings-NG (Bandit) (parser específico)
        recordIssues tools: [bandit(pattern: 'bandit.log')]

        archiveArtifacts artifacts: 'bandit.log,bandit.json,bandit.count', fingerprint: true, allowEmptyArchive: true

        script {
          def count = readFile('bandit.count').trim().split('=')[1] as int
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
        // Debe ser 5 hilos, 40 suma + 40 resta, y flask levantado. :contentReference[oaicite:13]{index=13}
        catchError(buildResult: 'SUCCESS', stageResult: 'FAILURE') {
          powershell '''
            # Arranca flask en background
            $flask = Start-Process -FilePath "python" -ArgumentList "-m","flask","run","--host=127.0.0.1","--port=5000" -PassThru -WindowStyle Hidden
            Start-Sleep -Seconds 2

            try {
              jmeter -n -t flask_cp12.jmx -l jmeter.jtl
            } finally {
              if ($flask -and !$flask.HasExited) { Stop-Process -Id $flask.Id -Force }
            }
          '''
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
        recordCoverage tools: [[parser: 'COBERTURA', pattern: 'coverage.xml']]
        archiveArtifacts artifacts: 'coverage.xml', fingerprint: true, allowEmptyArchive: true

        script {
          // Lee ratios desde coverage.xml (Cobertura)
          powershell '''
            [xml]$x = Get-Content coverage.xml
            $line = [double]$x.coverage.'line-rate' * 100.0
            $branch = [double]$x.coverage.'branch-rate' * 100.0
            "LINE_RATE=$line"   | Out-File coverage.line -Encoding ascii
            "BRANCH_RATE=$branch" | Out-File coverage.branch -Encoding ascii
            Write-Host ("Coverage => Lines: {0:N2}%, Branches: {1:N2}%" -f $line, $branch)
          '''

          def line = (readFile('coverage.line').trim().split('=')[1] as double)
          def branch = (readFile('coverage.branch').trim().split('=')[1] as double)

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
            if (stageRes != 'SUCCESS') { error("Coverage fuera de baremo => ${stageRes}. " + msg) } else { echo(msg) }
          }
        }
      }
    }
  }

  post {
    always {
      script {
        // Aplica el peor estado al build final (lo que te faltaba)
        currentBuild.result = env.BUILD_HEALTH
        echo "Build health final => ${currentBuild.result}"
      }
    }
  }
}

// Helper: peor de dos estados
def worst(String a, String b) {
  def order = ['SUCCESS': 0, 'UNSTABLE': 1, 'FAILURE': 2]
  return (order[b] > order[a]) ? b : a
}
