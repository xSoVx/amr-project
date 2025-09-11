"""
Pact broker configuration and utilities for CI/CD pipeline integration.

This module provides configuration for Pact broker integration,
contract publishing, and provider verification setup.
"""

import os
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class PactBrokerConfig:
    """Configuration for Pact broker connection and authentication."""
    
    broker_url: str
    username: Optional[str] = None
    password: Optional[str] = None
    token: Optional[str] = None
    consumer_name: str = "amr-consumer"
    provider_name: str = "amr-classification-service"
    consumer_version: Optional[str] = None
    provider_version: Optional[str] = None
    branch: Optional[str] = None
    build_url: Optional[str] = None
    tags: Optional[list] = None


def get_pact_broker_config() -> PactBrokerConfig:
    """
    Get Pact broker configuration from environment variables.
    
    Environment variables:
    - PACT_BROKER_URL: Pact broker base URL
    - PACT_BROKER_USERNAME: Username for authentication
    - PACT_BROKER_PASSWORD: Password for authentication
    - PACT_BROKER_TOKEN: Bearer token for authentication
    - PACT_CONSUMER_VERSION: Consumer application version
    - PACT_PROVIDER_VERSION: Provider application version
    - GIT_BRANCH or BRANCH_NAME: Git branch name
    - BUILD_URL: CI/CD build URL
    - PACT_TAGS: Comma-separated list of tags
    
    Returns:
        PactBrokerConfig: Configuration object with broker settings
        
    Raises:
        ValueError: If required configuration is missing
    """
    broker_url = os.getenv("PACT_BROKER_URL")
    if not broker_url:
        raise ValueError("PACT_BROKER_URL environment variable is required")
    
    # Authentication - prefer token over username/password
    token = os.getenv("PACT_BROKER_TOKEN")
    username = os.getenv("PACT_BROKER_USERNAME")
    password = os.getenv("PACT_BROKER_PASSWORD")
    
    if not token and not (username and password):
        logger.warning("No Pact broker authentication configured")
    
    # Version information
    consumer_version = os.getenv("PACT_CONSUMER_VERSION") or os.getenv("APP_VERSION")
    provider_version = os.getenv("PACT_PROVIDER_VERSION") or os.getenv("APP_VERSION")
    
    # Git branch information
    branch = (
        os.getenv("GIT_BRANCH") or 
        os.getenv("BRANCH_NAME") or 
        os.getenv("CI_COMMIT_REF_NAME") or
        os.getenv("GITHUB_REF_NAME")
    )
    
    # Build information
    build_url = (
        os.getenv("BUILD_URL") or 
        os.getenv("CI_JOB_URL") or
        os.getenv("GITHUB_SERVER_URL")
    )
    
    # Tags
    tags_str = os.getenv("PACT_TAGS")
    tags = tags_str.split(",") if tags_str else None
    
    return PactBrokerConfig(
        broker_url=broker_url,
        username=username,
        password=password,
        token=token,
        consumer_version=consumer_version,
        provider_version=provider_version,
        branch=branch,
        build_url=build_url,
        tags=tags
    )


def get_pact_publish_command() -> str:
    """
    Generate pact-broker publish command for CI/CD.
    
    Returns:
        str: Complete pact-broker CLI command for publishing contracts
    """
    config = get_pact_broker_config()
    
    # Base command
    cmd = ["pact-broker", "publish"]
    
    # Pact files location
    pact_dir = Path("tests/pacts")
    cmd.extend([str(pact_dir / "*.json")])
    
    # Broker URL
    cmd.extend(["--broker-base-url", config.broker_url])
    
    # Authentication
    if config.token:
        cmd.extend(["--broker-token", config.token])
    elif config.username and config.password:
        cmd.extend(["--broker-username", config.username])
        cmd.extend(["--broker-password", config.password])
    
    # Consumer version
    if config.consumer_version:
        cmd.extend(["--consumer-app-version", config.consumer_version])
    
    # Branch
    if config.branch:
        cmd.extend(["--branch", config.branch])
    
    # Build URL
    if config.build_url:
        cmd.extend(["--build-url", config.build_url])
    
    # Tags
    if config.tags:
        for tag in config.tags:
            cmd.extend(["--tag", tag.strip()])
    
    return " ".join(cmd)


def get_pact_verify_command() -> str:
    """
    Generate pact-broker verify command for provider testing.
    
    Returns:
        str: Complete pact-broker CLI command for provider verification
    """
    config = get_pact_broker_config()
    
    # Base command
    cmd = ["pact-broker", "verify"]
    
    # Provider details
    cmd.extend(["--provider", config.provider_name])
    cmd.extend(["--provider-base-url", "http://localhost:8080"])
    
    # Broker URL
    cmd.extend(["--broker-base-url", config.broker_url])
    
    # Authentication
    if config.token:
        cmd.extend(["--broker-token", config.token])
    elif config.username and config.password:
        cmd.extend(["--broker-username", config.username])
        cmd.extend(["--broker-password", config.password])
    
    # Provider version
    if config.provider_version:
        cmd.extend(["--provider-app-version", config.provider_version])
    
    # Provider states URL
    cmd.extend(["--provider-states-setup-url", "http://localhost:8080/_pact/provider-states"])
    
    # Publish verification results
    cmd.extend(["--publish-verification-results"])
    
    # Build URL
    if config.build_url:
        cmd.extend(["--build-url", config.build_url])
    
    return " ".join(cmd)


def get_can_i_deploy_command() -> str:
    """
    Generate can-i-deploy command to check deployment safety.
    
    Returns:
        str: Complete can-i-deploy CLI command
    """
    config = get_pact_broker_config()
    
    # Base command
    cmd = ["pact-broker", "can-i-deploy"]
    
    # Application details
    cmd.extend(["--pacticipant", config.consumer_name])
    if config.consumer_version:
        cmd.extend(["--version", config.consumer_version])
    
    cmd.extend(["--pacticipant", config.provider_name])
    if config.provider_version:
        cmd.extend(["--version", config.provider_version])
    
    # Broker URL
    cmd.extend(["--broker-base-url", config.broker_url])
    
    # Authentication
    if config.token:
        cmd.extend(["--broker-token", config.token])
    elif config.username and config.password:
        cmd.extend(["--broker-username", config.username])
        cmd.extend(["--broker-password", config.password])
    
    return " ".join(cmd)


def create_docker_compose_pact_broker() -> str:
    """
    Generate Docker Compose configuration for local Pact broker.
    
    Returns:
        str: Docker Compose YAML content for Pact broker setup
    """
    return """
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: pact_broker
      POSTGRES_PASSWORD: pact_broker
      POSTGRES_DB: pact_broker
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U pact_broker"]
      interval: 30s
      timeout: 10s
      retries: 3

  pact-broker:
    image: pactfoundation/pact-broker:latest
    environment:
      PACT_BROKER_DATABASE_URL: "postgresql://pact_broker:pact_broker@postgres:5432/pact_broker"
      PACT_BROKER_BASIC_AUTH_USERNAME: admin
      PACT_BROKER_BASIC_AUTH_PASSWORD: admin
      PACT_BROKER_PUBLIC_HEARTBEAT: "true"
      PACT_BROKER_ALLOW_PUBLIC_READ: "true"
    ports:
      - "9292:9292"
    depends_on:
      postgres:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "wget", "-q", "--spider", "http://localhost:9292/diagnostic/status/heartbeat"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  postgres_data:
"""


def create_github_actions_workflow() -> str:
    """
    Generate GitHub Actions workflow for Pact contract testing.
    
    Returns:
        str: GitHub Actions YAML workflow content
    """
    return """
name: Pact Contract Testing

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

env:
  PACT_BROKER_URL: ${{ secrets.PACT_BROKER_URL }}
  PACT_BROKER_TOKEN: ${{ secrets.PACT_BROKER_TOKEN }}
  PACT_CONSUMER_VERSION: ${{ github.sha }}
  PACT_PROVIDER_VERSION: ${{ github.sha }}

jobs:
  consumer-tests:
    name: Consumer Contract Tests
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -e ".[dev]"
    
    - name: Run consumer contract tests
      run: |
        pytest tests/pact/ -v --tb=short
    
    - name: Publish contracts to broker
      if: github.ref == 'refs/heads/main'
      run: |
        pip install pact-python
        pact-broker publish tests/pacts/*.json \\
          --broker-base-url $PACT_BROKER_URL \\
          --broker-token $PACT_BROKER_TOKEN \\
          --consumer-app-version $PACT_CONSUMER_VERSION \\
          --branch ${{ github.ref_name }} \\
          --build-url ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}

  provider-tests:
    name: Provider Contract Verification
    runs-on: ubuntu-latest
    needs: consumer-tests
    if: github.ref == 'refs/heads/main'
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -e ".[dev]"
        pip install pact-python
    
    - name: Start AMR service
      run: |
        uvicorn amr_engine.main:app --host 0.0.0.0 --port 8080 &
        sleep 10
        curl -f http://localhost:8080/health || exit 1
      env:
        AMR_RULES_PATH: amr_engine/rules/eucast_v_2025_1.yaml
    
    - name: Verify provider contracts
      run: |
        pact-broker verify \\
          --provider amr-classification-service \\
          --provider-base-url http://localhost:8080 \\
          --broker-base-url $PACT_BROKER_URL \\
          --broker-token $PACT_BROKER_TOKEN \\
          --provider-app-version $PACT_PROVIDER_VERSION \\
          --publish-verification-results \\
          --build-url ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}

  can-i-deploy:
    name: Check deployment safety
    runs-on: ubuntu-latest
    needs: [consumer-tests, provider-tests]
    if: github.ref == 'refs/heads/main'
    
    steps:
    - name: Check if safe to deploy
      run: |
        pip install pact-python
        pact-broker can-i-deploy \\
          --pacticipant amr-consumer \\
          --version $PACT_CONSUMER_VERSION \\
          --pacticipant amr-classification-service \\
          --version $PACT_PROVIDER_VERSION \\
          --broker-base-url $PACT_BROKER_URL \\
          --broker-token $PACT_BROKER_TOKEN
      env:
        PACT_BROKER_URL: ${{ secrets.PACT_BROKER_URL }}
        PACT_BROKER_TOKEN: ${{ secrets.PACT_BROKER_TOKEN }}
        PACT_CONSUMER_VERSION: ${{ github.sha }}
        PACT_PROVIDER_VERSION: ${{ github.sha }}
"""


def create_gitlab_ci_pipeline() -> str:
    """
    Generate GitLab CI pipeline for Pact contract testing.
    
    Returns:
        str: GitLab CI YAML pipeline content
    """
    return """
stages:
  - test
  - verify
  - deploy-check

variables:
  PACT_BROKER_URL: $PACT_BROKER_URL
  PACT_BROKER_TOKEN: $PACT_BROKER_TOKEN
  PACT_CONSUMER_VERSION: $CI_COMMIT_SHA
  PACT_PROVIDER_VERSION: $CI_COMMIT_SHA

.python_setup: &python_setup
  image: python:3.11
  before_script:
    - python -m pip install --upgrade pip
    - pip install -e ".[dev]"

consumer_tests:
  <<: *python_setup
  stage: test
  script:
    - pytest tests/pact/ -v --tb=short
  artifacts:
    paths:
      - tests/pacts/*.json
    expire_in: 1 week

publish_contracts:
  <<: *python_setup
  stage: test
  dependencies:
    - consumer_tests
  script:
    - pip install pact-python
    - |
      pact-broker publish tests/pacts/*.json \\
        --broker-base-url $PACT_BROKER_URL \\
        --broker-token $PACT_BROKER_TOKEN \\
        --consumer-app-version $PACT_CONSUMER_VERSION \\
        --branch $CI_COMMIT_REF_NAME \\
        --build-url $CI_JOB_URL
  only:
    - main
    - develop

provider_verification:
  <<: *python_setup
  stage: verify
  dependencies:
    - publish_contracts
  services:
    - name: redis:7-alpine
      alias: redis
  script:
    - pip install pact-python
    - |
      uvicorn amr_engine.main:app --host 0.0.0.0 --port 8080 &
      sleep 10
      curl -f http://localhost:8080/health || exit 1
    - |
      pact-broker verify \\
        --provider amr-classification-service \\
        --provider-base-url http://localhost:8080 \\
        --broker-base-url $PACT_BROKER_URL \\
        --broker-token $PACT_BROKER_TOKEN \\
        --provider-app-version $PACT_PROVIDER_VERSION \\
        --publish-verification-results \\
        --build-url $CI_JOB_URL
  environment:
    name: test
  variables:
    AMR_RULES_PATH: amr_engine/rules/eucast_v_2025_1.yaml
    REDIS_ENABLED: "false"
  only:
    - main
    - develop

can_i_deploy:
  image: python:3.11
  stage: deploy-check
  dependencies:
    - provider_verification
  script:
    - pip install pact-python
    - |
      pact-broker can-i-deploy \\
        --pacticipant amr-consumer \\
        --version $PACT_CONSUMER_VERSION \\
        --pacticipant amr-classification-service \\
        --version $PACT_PROVIDER_VERSION \\
        --broker-base-url $PACT_BROKER_URL \\
        --broker-token $PACT_BROKER_TOKEN
  only:
    - main
"""


def create_jenkins_pipeline() -> str:
    """
    Generate Jenkins pipeline for Pact contract testing.
    
    Returns:
        str: Jenkins pipeline Groovy script content
    """
    return """
pipeline {
    agent any
    
    environment {
        PACT_BROKER_URL = credentials('pact-broker-url')
        PACT_BROKER_TOKEN = credentials('pact-broker-token')
        PACT_CONSUMER_VERSION = "${env.GIT_COMMIT}"
        PACT_PROVIDER_VERSION = "${env.GIT_COMMIT}"
        PYTHON_VERSION = '3.11'
    }
    
    stages {
        stage('Setup') {
            steps {
                sh '''
                    python -m pip install --upgrade pip
                    pip install -e ".[dev]"
                '''
            }
        }
        
        stage('Consumer Tests') {
            steps {
                sh 'pytest tests/pact/ -v --tb=short --junitxml=test-results.xml'
            }
            post {
                always {
                    publishTestResults testResultsPattern: 'test-results.xml'
                    archiveArtifacts artifacts: 'tests/pacts/*.json', fingerprint: true
                }
            }
        }
        
        stage('Publish Contracts') {
            when {
                anyOf {
                    branch 'main'
                    branch 'develop'
                }
            }
            steps {
                sh '''
                    pip install pact-python
                    pact-broker publish tests/pacts/*.json \\
                        --broker-base-url $PACT_BROKER_URL \\
                        --broker-token $PACT_BROKER_TOKEN \\
                        --consumer-app-version $PACT_CONSUMER_VERSION \\
                        --branch $BRANCH_NAME \\
                        --build-url $BUILD_URL
                '''
            }
        }
        
        stage('Provider Verification') {
            when {
                anyOf {
                    branch 'main'
                    branch 'develop'
                }
            }
            environment {
                AMR_RULES_PATH = 'amr_engine/rules/eucast_v_2025_1.yaml'
                REDIS_ENABLED = 'false'
            }
            steps {
                sh '''
                    pip install pact-python
                    uvicorn amr_engine.main:app --host 0.0.0.0 --port 8080 &
                    SERVICE_PID=$!
                    sleep 10
                    curl -f http://localhost:8080/health || exit 1
                    
                    pact-broker verify \\
                        --provider amr-classification-service \\
                        --provider-base-url http://localhost:8080 \\
                        --broker-base-url $PACT_BROKER_URL \\
                        --broker-token $PACT_BROKER_TOKEN \\
                        --provider-app-version $PACT_PROVIDER_VERSION \\
                        --publish-verification-results \\
                        --build-url $BUILD_URL
                    
                    kill $SERVICE_PID
                '''
            }
        }
        
        stage('Can I Deploy?') {
            when {
                branch 'main'
            }
            steps {
                sh '''
                    pip install pact-python
                    pact-broker can-i-deploy \\
                        --pacticipant amr-consumer \\
                        --version $PACT_CONSUMER_VERSION \\
                        --pacticipant amr-classification-service \\
                        --version $PACT_PROVIDER_VERSION \\
                        --broker-base-url $PACT_BROKER_URL \\
                        --broker-token $PACT_BROKER_TOKEN
                '''
            }
        }
    }
    
    post {
        always {
            cleanWs()
        }
    }
}
"""