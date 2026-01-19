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
            $p = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "& .venv\\Scripts\\python.exe app\\api.py" -PassThru
            $flaskPid = $p.Id
            Start-Sleep 3

            & .venv\\Scripts\\python.exe -m pytest test\\rest --junitxml=result-rest.xml

            Stop-Process -Id $flaskPid -Force
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
            & .venv\\Scripts\\python.exe -m flake8 app test --count --statistics > flake8.log
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
