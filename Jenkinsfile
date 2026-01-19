pipeline {
  agent any

  options {
    timestamps()
  }

  environment {
    PY = 'py -3.11'

    FLASK_HOST = '127.0.0.1'
    FLASK_PORT = '5000'
    WIREMOCK_PORT = '9090'

    FLASK_PID_FILE = 'flask.pid'
    WIREMOCK_PID_FILE = 'wiremock.pid'

    WM_DIR = 'tools\\wiremock'
    WM_JAR = 'tools\\wiremock\\wiremock-standalone-3.13.2.jar'
    WM_URL = 'https://repo1.maven.org/maven2/org/wiremock/wiremock-standalone/3.13.2/wiremock-standalone-3.13.2.jar'
  }

  stages {

    stage('Checkout') {
      steps {
        checkout scm
      }
    }

    stage('Diagnostico (entorno Jenkins)') {
      steps {
        powershell '''
          $ErrorActionPreference = 'Continue'

          Write-Host "=== WHOAMI ==="
          whoami

          Write-Host "=== COMPUTERNAME ==="
          Write-Host $env:COMPUTERNAME

          Write-Host "=== WORKSPACE ==="
          Write-Host $env:WORKSPACE

          Write-Host "=== PATH (recortado) ==="
          ($env:Path -split ';' | Select-Object -First 15) | ForEach-Object { Write-Host "  $_" }
          Write-Host "  ..."

          Write-Host "=== PY LAUNCHER LIST ==="
          try { py -0p } catch { Write-Host ("py -0p ERROR: " + $_.Exception.Message) }

          Write-Host "=== PY (FORZADO) ==="
          try { py -3.11 --version } catch { Write-Host ("py -3.11 --version ERROR: " + $_.Exception.Message) }
          try { py -3.11 -c "import sys; print(sys.executable)" } catch { Write-Host ("sys.executable ERROR: " + $_.Exception.Message) }

          Write-Host "=== WHERE py/python ==="
          try { where.exe py } catch { Write-Host "where py ERROR" }
          try { where.exe python } catch { Write-Host "where python ERROR" }

          Write-Host "=== JAVA ==="
          try { where.exe java } catch { Write-Host "where java ERROR" }
          try { java -version } catch { Write-Host ("java -version ERROR: " + $_.Exception.Message) }

          Write-Host "=== Puertos en uso (5000/9090) ==="
          try { netstat -ano | findstr (":" + $env:FLASK_PORT + " ") } catch { }
          try { netstat -ano | findstr (":" + $env:WIREMOCK_PORT + " ") } catch { }
        '''
      }
    }

    stage('Unit') {
      steps {
        powershell '''
          $ErrorActionPreference = 'Stop'
          py -3.11 -m pytest --junitxml=result-unit.xml test\\unit
        '''
      }
      post {
        always {
          junit allowEmptyResults: true, testResults: 'result-unit.xml'
          archiveArtifacts allowEmptyArchive: true, artifacts: 'result-unit.xml'
        }
      }
    }

    stage('REST (Flask + WireMock + tests)') {
      steps {
        powershell '''
          $ErrorActionPreference = 'Stop'

          function Wait-Port([string]$host, [int]$port, [int]$seconds) {
            $deadline = (Get-Date).AddSeconds($seconds)
            while ((Get-Date) -lt $deadline) {
              try {
                $c = New-Object System.Net.Sockets.TcpClient
                $iar = $c.BeginConnect($host, $port, $null, $null)
                if ($iar.AsyncWaitHandle.WaitOne(300)) {
                  $c.EndConnect($iar)
                  $c.Close()
                  return
                }
                $c.Close()
              } catch { }
              Start-Sleep -Milliseconds 300
            }
            throw "Timeout esperando puerto $host:$port"
          }

          function Stop-ByPidFile([string]$file) {
            if (Test-Path $file) {
              $procId = (Get-Content $file | Select-Object -First 1)
              if ($procId) {
                Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
              }
              Remove-Item $file -Force -ErrorAction SilentlyContinue
            }
          }

          # Limpieza previa (por si quedó algo de antes)
          Stop-ByPidFile "flask.pid"
          Stop-ByPidFile "wiremock.pid"

          # Preparar WireMock jar
          New-Item -ItemType Directory -Force -Path "tools\\wiremock" | Out-Null
          if (!(Test-Path "tools\\wiremock\\wiremock-standalone-3.13.2.jar")) {
            Write-Host "Descargando WireMock..."
            Invoke-WebRequest -Uri "https://repo1.maven.org/maven2/org/wiremock/wiremock-standalone/3.13.2/wiremock-standalone-3.13.2.jar" -OutFile "tools\\wiremock\\wiremock-standalone-3.13.2.jar" -UseBasicParsing
          }

          # Arrancar WireMock
          $wmProc = Start-Process -FilePath "java" -ArgumentList @(
            "-jar","tools\\wiremock\\wiremock-standalone-3.13.2.jar",
            "--port","9090",
            "--root-dir","test\\wiremock"
          ) -PassThru -WindowStyle Hidden
          $wmProc.Id | Out-File -Encoding ascii "wiremock.pid"
          Write-Host ("WireMock PID: " + $wmProc.Id)

          # Arrancar Flask
          $flProc = Start-Process -FilePath "cmd.exe" -ArgumentList @(
            "/c",
            "py -3.11 -m flask --app app/api.py run --host 127.0.0.1 --port 5000"
          ) -PassThru -WindowStyle Hidden
          $flProc.Id | Out-File -Encoding ascii "flask.pid"
          Write-Host ("Flask PID: " + $flProc.Id)

          # Esperar puertos
          Wait-Port "127.0.0.1" 9090 40
          Wait-Port "127.0.0.1" 5000 40

          # Ejecutar REST tests
          py -3.11 -m pytest --junitxml=result-rest.xml test\\rest
        '''
      }

      post {
        always {
          powershell '''
            $ErrorActionPreference = 'SilentlyContinue'

            function Stop-ByPidFile([string]$file) {
              if (Test-Path $file) {
                $procId = (Get-Content $file | Select-Object -First 1)
                if ($procId) {
                  Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
                }
                Remove-Item $file -Force -ErrorAction SilentlyContinue
              }
            }

            Stop-ByPidFile "flask.pid"
            Stop-ByPidFile "wiremock.pid"
          '''
          junit allowEmptyResults: true, testResults: 'result-rest.xml'
          archiveArtifacts allowEmptyArchive: true, artifacts: 'result-rest.xml'
        }
      }
    }
  }
}
