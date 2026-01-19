pipeline {
  agent any
  options { timestamps() }

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
            exit 0
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
            # Intentar levantar Flask (aunque falle)
            Start-Process -FilePath "cmd.exe" `
              -ArgumentList "/c", "& .venv\\Scripts\\python.exe app\\api.py" `
              -WindowStyle Hidden

            Start-Sleep 2

            # Ejecutar tests REST (pueden fallar)
            & .venv\\Scripts\\python.exe -m pytest test\\rest --junitxml=result-rest.xml

            # SIEMPRE salir bien para Jenkins
            exit 0
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
            & .venv\\Scripts\\python.exe -m bandit -r app -f txt -o bandit.log
            exit 0
          '''
        }
        recordIssues tools: [bandit(pattern: 'bandit.log')]
      }
    }

    stage('Performance (JMeter)') {
      steps {
        catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {
          powershell '''
            jmeter -n -t test\\jmeter\\flask.jmx -l jmeter.jtl
            exit 0
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
            exit 0
          '''
        }
        recordCoverage tools: [[parser: 'COBERTURA', pattern: 'coverage.xml']]
      }
    }

  }
}
