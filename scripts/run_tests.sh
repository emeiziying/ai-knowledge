#!/bin/bash

# Comprehensive test runner script for AI Knowledge Base

set -e

echo "🧪 Running AI Knowledge Base Test Suite"
echo "======================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if we're in the right directory
if [ ! -f "docker-compose.yml" ]; then
    print_error "Please run this script from the project root directory"
    exit 1
fi

# Parse command line arguments
RUN_BACKEND=true
RUN_FRONTEND=true
RUN_E2E=false
RUN_PERFORMANCE=false
COVERAGE=true
VERBOSE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --backend-only)
            RUN_FRONTEND=false
            shift
            ;;
        --frontend-only)
            RUN_BACKEND=false
            shift
            ;;
        --e2e)
            RUN_E2E=true
            shift
            ;;
        --performance)
            RUN_PERFORMANCE=true
            shift
            ;;
        --no-coverage)
            COVERAGE=false
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --backend-only    Run only backend tests"
            echo "  --frontend-only   Run only frontend tests"
            echo "  --e2e            Run end-to-end tests"
            echo "  --performance    Run performance tests"
            echo "  --no-coverage    Skip coverage reporting"
            echo "  --verbose        Verbose output"
            echo "  --help           Show this help message"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Create test results directory
mkdir -p test-results

# Backend Tests
if [ "$RUN_BACKEND" = true ]; then
    print_status "Running Backend Tests..."
    
    cd backend
    
    # Install dependencies if needed
    if [ ! -d "venv" ]; then
        print_status "Creating Python virtual environment..."
        python -m venv venv
    fi
    
    source venv/bin/activate
    
    # Install test dependencies
    print_status "Installing test dependencies..."
    pip install -r requirements.txt
    pip install pytest pytest-asyncio pytest-cov httpx
    
    # Run unit tests
    print_status "Running unit tests..."
    if [ "$COVERAGE" = true ]; then
        if [ "$VERBOSE" = true ]; then
            pytest tests/ -v --cov=app --cov-report=html --cov-report=term-missing -m "not integration and not performance and not e2e"
        else
            pytest tests/ --cov=app --cov-report=html --cov-report=term-missing -m "not integration and not performance and not e2e"
        fi
    else
        if [ "$VERBOSE" = true ]; then
            pytest tests/ -v -m "not integration and not performance and not e2e"
        else
            pytest tests/ -m "not integration and not performance and not e2e"
        fi
    fi
    
    if [ $? -eq 0 ]; then
        print_success "Backend unit tests passed!"
    else
        print_error "Backend unit tests failed!"
        exit 1
    fi
    
    # Run integration tests
    print_status "Running integration tests..."
    if [ "$VERBOSE" = true ]; then
        pytest tests/ -v -m "integration"
    else
        pytest tests/ -m "integration"
    fi
    
    if [ $? -eq 0 ]; then
        print_success "Backend integration tests passed!"
    else
        print_error "Backend integration tests failed!"
        exit 1
    fi
    
    # Run performance tests if requested
    if [ "$RUN_PERFORMANCE" = true ]; then
        print_status "Running performance tests..."
        if [ "$VERBOSE" = true ]; then
            pytest tests/ -v -m "performance"
        else
            pytest tests/ -m "performance"
        fi
        
        if [ $? -eq 0 ]; then
            print_success "Backend performance tests passed!"
        else
            print_warning "Some performance tests failed or were slow"
        fi
    fi
    
    deactivate
    cd ..
fi

# Frontend Tests
if [ "$RUN_FRONTEND" = true ]; then
    print_status "Running Frontend Tests..."
    
    cd frontend
    
    # Install dependencies if needed
    if [ ! -d "node_modules" ]; then
        print_status "Installing Node.js dependencies..."
        npm install
    fi
    
    # Run unit tests
    print_status "Running frontend unit tests..."
    if [ "$COVERAGE" = true ]; then
        npm run test -- --coverage --watchAll=false
    else
        npm run test -- --watchAll=false
    fi
    
    if [ $? -eq 0 ]; then
        print_success "Frontend tests passed!"
    else
        print_error "Frontend tests failed!"
        exit 1
    fi
    
    # Run linting
    print_status "Running ESLint..."
    npm run lint
    
    if [ $? -eq 0 ]; then
        print_success "Frontend linting passed!"
    else
        print_warning "Frontend linting issues found"
    fi
    
    # Type checking
    print_status "Running TypeScript type checking..."
    npx tsc --noEmit
    
    if [ $? -eq 0 ]; then
        print_success "TypeScript type checking passed!"
    else
        print_error "TypeScript type checking failed!"
        exit 1
    fi
    
    cd ..
fi

# End-to-End Tests
if [ "$RUN_E2E" = true ]; then
    print_status "Running End-to-End Tests..."
    
    # Start services
    print_status "Starting services for E2E tests..."
    docker-compose -f docker-compose.yml up -d --build
    
    # Wait for services to be ready
    print_status "Waiting for services to be ready..."
    sleep 30
    
    # Health check
    print_status "Checking service health..."
    curl -f http://localhost:8000/health || {
        print_error "Backend service is not healthy"
        docker-compose logs
        docker-compose down
        exit 1
    }
    
    curl -f http://localhost:3000 || {
        print_error "Frontend service is not healthy"
        docker-compose logs
        docker-compose down
        exit 1
    }
    
    # Run E2E tests
    cd backend
    source venv/bin/activate
    
    if [ "$VERBOSE" = true ]; then
        pytest tests/ -v -m "e2e"
    else
        pytest tests/ -m "e2e"
    fi
    
    E2E_RESULT=$?
    
    deactivate
    cd ..
    
    # Cleanup
    print_status "Stopping services..."
    docker-compose down
    
    if [ $E2E_RESULT -eq 0 ]; then
        print_success "End-to-end tests passed!"
    else
        print_error "End-to-end tests failed!"
        exit 1
    fi
fi

# Generate test report
print_status "Generating test report..."

cat > test-results/test-summary.md << EOF
# Test Results Summary

Generated on: $(date)

## Test Configuration
- Backend Tests: $RUN_BACKEND
- Frontend Tests: $RUN_FRONTEND
- E2E Tests: $RUN_E2E
- Performance Tests: $RUN_PERFORMANCE
- Coverage Enabled: $COVERAGE

## Results
EOF

if [ "$RUN_BACKEND" = true ]; then
    echo "- ✅ Backend unit tests: PASSED" >> test-results/test-summary.md
    echo "- ✅ Backend integration tests: PASSED" >> test-results/test-summary.md
fi

if [ "$RUN_FRONTEND" = true ]; then
    echo "- ✅ Frontend tests: PASSED" >> test-results/test-summary.md
    echo "- ✅ TypeScript checking: PASSED" >> test-results/test-summary.md
fi

if [ "$RUN_E2E" = true ]; then
    echo "- ✅ End-to-end tests: PASSED" >> test-results/test-summary.md
fi

if [ "$RUN_PERFORMANCE" = true ]; then
    echo "- ✅ Performance tests: COMPLETED" >> test-results/test-summary.md
fi

echo "" >> test-results/test-summary.md
echo "## Coverage Reports" >> test-results/test-summary.md

if [ "$COVERAGE" = true ] && [ "$RUN_BACKEND" = true ]; then
    echo "- Backend coverage: Available in \`backend/htmlcov/index.html\`" >> test-results/test-summary.md
fi

if [ "$COVERAGE" = true ] && [ "$RUN_FRONTEND" = true ]; then
    echo "- Frontend coverage: Available in \`frontend/coverage/lcov-report/index.html\`" >> test-results/test-summary.md
fi

print_success "All tests completed successfully!"
print_status "Test summary available in: test-results/test-summary.md"

if [ "$COVERAGE" = true ]; then
    print_status "Coverage reports:"
    if [ "$RUN_BACKEND" = true ]; then
        echo "  - Backend: backend/htmlcov/index.html"
    fi
    if [ "$RUN_FRONTEND" = true ]; then
        echo "  - Frontend: frontend/coverage/lcov-report/index.html"
    fi
fi