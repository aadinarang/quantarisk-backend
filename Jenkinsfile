pipeline {
    agent any

    environment {
        IMAGE_NAME = 'quantarisk-backend'
        CONTAINER_NAME = 'quantarisk-backend'
    }

    stages {

        stage('Checkout') {
            steps {
                echo 'Checking out code from GitHub...'
                checkout scm
            }
        }

        stage('Install Dependencies') {
            steps {
                echo 'Installing Python dependencies...'
                bat 'pip install -r requirements.txt'
            }
        }

        stage('Run Tests') {
            steps {
                echo 'Running automated tests (CT layer)...'
                bat 'pip install pytest httpx'
                bat 'pytest tests/ -v --tb=short'
            }
        }

        stage('Docker Build') {
            steps {
                echo 'Building Docker image...'
                bat 'docker build -t %IMAGE_NAME% .'
            }
        }

        stage('Deploy') {
            steps {
                echo 'Deploying with docker-compose...'
                bat 'docker-compose down'
                bat 'docker-compose up -d'
            }
        }

    }

    post {
        success {
            echo 'Pipeline completed successfully. QuantaRisk is live.'
        }
        failure {
            echo 'Pipeline failed. Check the logs above for errors.'
        }
    }
}
