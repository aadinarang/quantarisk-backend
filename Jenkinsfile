pipeline {
    agent any

    stages {

        stage('Checkout') {
            steps {
                echo 'Checking out code from GitHub...'
                checkout scm
            }
        }

        stage('Debug') {
            steps {
                sh 'ls -la'
                sh 'cat run_tests.sh'
                sh 'docker run --rm -v $(pwd):/app -w /app python:3.11-slim ls -la /app'
            }
        }

        stage('Run Tests') {
            steps {
                sh 'docker run --rm -v $(pwd):/app -w /app -e PYTHONPATH=/app -e DATABASE_URL=sqlite:///./quantarisk.db python:3.11-slim bash /app/run_tests.sh'
            }
        }

        stage('Docker Build') {
            steps {
                sh 'docker build -t quantarisk-backend .'
            }
        }

        stage('Deploy') {
            steps {
                sh 'docker-compose down || true'
                sh 'docker-compose up -d'
            }
        }

    }

    post {
        success {
            echo 'Pipeline completed. QuantaRisk is live.'
        }
        failure {
            echo 'Pipeline failed. Check logs above.'
        }
    }
}
