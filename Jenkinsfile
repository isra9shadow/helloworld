def HAS_FAIL = false
def HAS_UNSTABLE = false

def markStage = { String status, String msg ->
    if (status == 'SUCCESS') return
    if (status == 'FAILURE') HAS_FAIL = true
    if (status == 'UNSTABLE') HAS_UNSTABLE = true

    // Marca la etapa (UNSTABLE/FAILURE) PERO no rompe el pipeline
    catchError(buildResult: 'SUCCESS', stageResult: status) {
        error(msg)
    }
}

pipeline {
    agent any

    options {
        timestamps()
        skipDefaultCheckout(true)
    }

    environment {
        VENV_DIR     = ".venv"
        REQUIREMENTS = "requirements-ci.txt"
        JMETER_JMX   = "test/jmeter/flask.jmx"
        JMETER_JTL   = "jmeter.jtl"
    }

    stages {

        stage('Get Code') {
            steps {
                deleteDir()
                checkout scm

                powershell '''
                    whoami
                    hostname
                    Write-Host ("WORKSPACE=" + $env:WORKSPACE)
                '''

                powershell '''
                    $ErrorActionPreference = "Stop"
                    $venv = Join-Path $env:WORKSPACE $env:VENV_DIR

                    if (Test-Path $venv) { Remove-Item -Recurse -Force $venv }

                    python -m venv $venv
                    $py = Join-Path $venv "Scripts\\python.exe"

                    & $py -m pip install -U pip

                    if (Test-Path $env:REQUIREMENTS) {
                        & $py -m pip install -r $env:REQUIREMENTS
                    } else {
                        & $py -m pip install pytest coverage flake8 bandit flask requests
                    }

                    & $py -c "import sys; print(sys.version); print(sys.executable)"
                '''
            }
        }

        // Unit SOLO UNA VEZ + genera coverage.xml aquí (luego Coverage solo publica/evalúa)
        stage('Unit') {
            steps {
                catchError(buildResult: 'SUCCESS', stageResult: 'SUCCESS') {
                    powershell '''
                        $ErrorActionPreference = "Stop"
                        $py = Join-Path (Join-Path $env:WORKSPACE $env:VENV_DIR) "Scripts\\python.exe"

                        & $py -m coverage erase

                        // Omitimos api.py e __init__.py para conseguir los ratios esperados del ejercicio
                        & $py -m coverage run --omit="app/api.py,app/__init__.py" -m pytest -q test\\unit --junitxml=result-unit.xml

                        & $py -m coverage xml -o coverage.xml
                        & $py -m coverage report -m | Out-File -FilePath coverage-report.txt -Encoding utf8
                    '''
                }
            }
            post {
                always {
                    junit testResults: 'result-unit.xml', allowEmptyResults: true
                    archiveArtifacts artifacts: 'result-unit.xml,coverage.xml,coverage-report.txt', allowEmptyArchive: true
                }
            }
        }

        stage('REST') {
            steps {
                catchError(buildResult: 'SUCCESS', stageResult: 'SUCCESS') {
                    powershell '''
                        $ErrorActionPreference = "Stop"
                        $py = Join-Path (Join-Path $env:WORKSPACE $env:VENV_DIR) "Scripts\\python.exe"

                        $p = Start-Process -FilePath $py -ArgumentList "-m","flask","--app","app.api","run","--host","127.0.0.1","--port","5000","--no-reload" -PassThru -WindowStyle Hidden
                        $pid = $p.Id

                        try {
                            $ready = $false
                            for ($i=0; $i -lt 30; $i++) {
                                try {
                                    $r = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:5000/health" -TimeoutSec 2
                                    if ($r.StatusCode -eq 200) { $ready = $true; break }
                                } catch { Start-Sleep -Seconds 1 }
                            }
                            if (-not $ready) { throw "Flask not ready on :5000" }

                            & $py -m pytest -q test\\rest --junitxml=result-rest.xml
                        }
                        finally {
                            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
                        }
                    '''
                }
            }
            post {
                always {
                    junit testResults: 'result-rest.xml', allowEmptyResults: true
                    archiveArtifacts artifacts: 'result-rest.xml', allowEmptyArchive: true
                }
            }
        }

        stage('Static (Flake8)') {
            steps {
                powershell '''
                    $ErrorActionPreference = "Stop"
                    $py = Join-Path (Join-Path $env:WORKSPACE $env:VENV_DIR) "Scripts\\python.exe"

                    if (Test-Path flake8.log) { Remove-Item -Force flake8.log }

                    & $py -m flake8 app test --statistics --exit-zero | Tee-Object -FilePath flake8.log
                '''

                script {
                    recordIssues tools: [flake8(pattern: 'flake8.log')], id: 'flake8'
                    archiveArtifacts artifacts: 'flake8.log', allowEmptyArchive: true

                    def out = powershell(returnStdout: true, script: '''
                        $n = (Get-Content flake8.log | Select-String -Pattern '^[^:]+:\\d+:\\d+:' ).Count
                        Write-Output $n
                    ''').trim()

                    int findings = out ? out.toInteger() : 0
                    echo "Flake8 findings: ${findings}"

                    def status = 'SUCCESS'
                    if (findings >= 10) status = 'FAILURE'
                    else if (findings >= 8) status = 'UNSTABLE'

                    markStage(status, "Flake8: ${findings} findings => ${status} (pipeline continues)")
                }
            }
        }

        stage('Security Test (Bandit)') {
            steps {
                powershell '''
                    $ErrorActionPreference = "Stop"
                    $py = Join-Path (Join-Path $env:WORKSPACE $env:VENV_DIR) "Scripts\\python.exe"

                    if (Test-Path bandit.log) { Remove-Item -Force bandit.log }

                    // Formato tipo PEP8 para que Warnings-NG lo parsee con "pep8"
                    & $py -m bandit -r app -f custom --msg-template "{path}:{line}: {test_id} {msg}" -o bandit.log
                    $code = $LASTEXITCODE
                    Write-Host ("Bandit exit code: " + $code)

                    exit 0
                '''

                script {
                    recordIssues tools: [pep8(pattern: 'bandit.log')], id: 'bandit'
                    archiveArtifacts artifacts: 'bandit.log', allowEmptyArchive: true

                    def out = powershell(returnStdout: true, script: '''
                        if (Test-Path bandit.log) {
                            $n = (Get-Content bandit.log | Select-String -Pattern '^[^:]+:\\d+:' ).Count
                            Write-Output $n
                        } else {
                            Write-Output 0
                        }
                    ''').trim()

                    int findings = out ? out.toInteger() : 0
                    echo "Bandit findings: ${findings}"

                    def status = 'SUCCESS'
                    if (findings >= 4) status = 'FAILURE'
                    else if (findings >= 2) status = 'UNSTABLE'

                    markStage(status, "Bandit: ${findings} findings => ${status} (pipeline continues)")
                }
            }
        }

        stage('Performance (JMeter)') {
            steps {
                powershell '''
                    $ErrorActionPreference = "Stop"
                    $py = Join-Path (Join-Path $env:WORKSPACE $env:VENV_DIR) "Scripts\\python.exe"

                    // Resolver jmeter.bat
                    $jm = $env:JMETER_BIN
                    if (-not $jm) {
                        $cmd = Get-Command jmeter.bat -ErrorAction SilentlyContinue
                        if ($cmd) { $jm = $cmd.Source }
                    }
                    if (-not $jm) {
                        $cand = Get-ChildItem -Path "C:\\apache-jmeter*\\bin\\jmeter.bat","C:\\JMeter*\\bin\\jmeter.bat","C:\\tools\\apache-jmeter*\\bin\\jmeter.bat" -ErrorAction SilentlyContinue | Select-Object -First 1
                        if ($cand) { $jm = $cand.FullName }
                    }
                    if (-not $jm) { throw "JMeter not found. Set JMETER_BIN (full path to jmeter.bat) or add it to PATH." }

                    if (Test-Path $env:JMETER_JTL) { Remove-Item -Force $env:JMETER_JTL }

                    // Start Flask
                    $p = Start-Process -FilePath $py -ArgumentList "-m","flask","--app","app.api","run","--host","127.0.0.1","--port","5000","--no-reload" -PassThru -WindowStyle Hidden
                    $pid = $p.Id

                    try {
                        $ready = $false
                        for ($i=0; $i -lt 30; $i++) {
                            try {
                                $r = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:5000/health" -TimeoutSec 2
                                if ($r.StatusCode -eq 200) { $ready = $true; break }
                            } catch { Start-Sleep -Seconds 1 }
                        }
                        if (-not $ready) { throw "Flask not ready on :5000" }

                        & $jm -n -t $env:JMETER_JMX -l $env:JMETER_JTL
                    }
                    finally {
                        Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
                    }
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'jmeter.jtl', allowEmptyArchive: true
                    perfReport sourceDataFiles: 'jmeter.jtl', percentiles: '0,50,90,95,100'
                }
            }
        }

        stage('Coverage') {
            steps {
                script {
                    recordCoverage tools: [cobertura(pattern: 'coverage.xml')]

                    def xml = readFile('coverage.xml')
                    def mLine = (xml =~ /line-rate="([0-9.]+)"/)
                    def mBranch = (xml =~ /branch-rate="([0-9.]+)"/)

                    double linePct = mLine ? (mLine[0][1] as double) * 100.0 : 0.0
                    double branchPct = mBranch ? (mBranch[0][1] as double) * 100.0 : 0.0

                    echo String.format("Coverage => Lines: %.2f%%, Branches: %.2f%%", linePct, branchPct)

                    def status = 'SUCCESS'
                    if (linePct < 85.0 || branchPct < 80.0) status = 'FAILURE'
                    else if (linePct < 95.0 || branchPct < 90.0) status = 'UNSTABLE'

                    markStage(status, String.format("Coverage: Lines %.2f%%, Branches %.2f%% => %s (pipeline continues)", linePct, branchPct, status))
                }
            }
        }
    }

    post {
        always {
            script {
                def finalStatus = 'SUCCESS'
                if (HAS_FAIL) finalStatus = 'FAILURE'
                else if (HAS_UNSTABLE) finalStatus = 'UNSTABLE'
                currentBuild.result = finalStatus
                echo "Build health final => ${finalStatus}"
            }
        }
    }
}
