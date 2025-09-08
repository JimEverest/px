"""
Comprehensive test runner for the px-ui-client test suite.
Provides test execution, reporting, and performance metrics.
"""

import pytest
import sys
import os
import time
import json
from datetime import datetime
from pathlib import Path
import argparse


class TestRunner:
    """Main test runner for comprehensive test suite."""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.test_results = {}
        self.performance_metrics = {}
    
    def run_unit_tests(self, verbose=False):
        """Run unit tests for data models, PAC validation, and event processing."""
        print("Running Unit Tests...")
        
        unit_test_files = [
            "tests/test_data_models.py",
            "tests/test_pac_validation.py", 
            "tests/test_event_processing.py"
        ]
        
        args = ["-v"] if verbose else []
        args.extend(unit_test_files)
        
        result = pytest.main(args)
        self.test_results['unit_tests'] = result
        return result == 0
    
    def run_integration_tests(self, verbose=False):
        """Run integration tests for proxy-UI communication."""
        print("Running Integration Tests...")
        
        integration_test_files = [
            "tests/test_integration_comprehensive.py"
        ]
        
        args = ["-v"] if verbose else []
        args.extend(integration_test_files)
        
        result = pytest.main(args)
        self.test_results['integration_tests'] = result
        return result == 0
    
    def run_performance_tests(self, verbose=False):
        """Run performance tests for high-volume scenarios."""
        print("Running Performance Tests...")
        
        performance_test_files = [
            "tests/test_performance.py"
        ]
        
        args = ["-v", "-s"]  # Always show output for performance tests
        if verbose:
            args.append("--tb=short")
        args.extend(performance_test_files)
        
        result = pytest.main(args)
        self.test_results['performance_tests'] = result
        return result == 0
    
    def run_automated_tests(self, verbose=False):
        """Run automated tests with test configurations."""
        print("Running Automated Scenario Tests...")
        
        automated_test_files = [
            "tests/test_automated_scenarios.py"
        ]
        
        args = ["-v"] if verbose else []
        args.extend(automated_test_files)
        
        result = pytest.main(args)
        self.test_results['automated_tests'] = result
        return result == 0
    
    def run_existing_tests(self, verbose=False):
        """Run existing test files to ensure compatibility."""
        print("Running Existing Tests...")
        
        existing_test_files = [
            "tests/test_config.py",
            "tests/test_enhanced_handler.py",
            "tests/test_event_communication.py",
            "tests/test_proxy_control.py",
            "tests/test_response_details_dialog.py"
        ]
        
        # Filter to only existing files
        existing_files = [f for f in existing_test_files if os.path.exists(f)]
        
        if existing_files:
            args = ["-v"] if verbose else []
            args.extend(existing_files)
            
            result = pytest.main(args)
            self.test_results['existing_tests'] = result
            return result == 0
        else:
            print("No existing test files found")
            self.test_results['existing_tests'] = 0
            return True
    
    def run_all_tests(self, verbose=False, skip_performance=False):
        """Run all test suites."""
        print("=" * 60)
        print("PX-UI-CLIENT COMPREHENSIVE TEST SUITE")
        print("=" * 60)
        
        self.start_time = time.time()
        
        results = {
            'unit_tests': self.run_unit_tests(verbose),
            'integration_tests': self.run_integration_tests(verbose),
            'automated_tests': self.run_automated_tests(verbose),
            'existing_tests': self.run_existing_tests(verbose)
        }
        
        if not skip_performance:
            results['performance_tests'] = self.run_performance_tests(verbose)
        
        self.end_time = time.time()
        
        # Generate report
        self.generate_report(results)
        
        # Return overall success
        return all(results.values())
    
    def generate_report(self, results):
        """Generate comprehensive test report."""
        total_time = self.end_time - self.start_time
        
        print("\n" + "=" * 60)
        print("TEST EXECUTION REPORT")
        print("=" * 60)
        
        print(f"Execution Time: {total_time:.2f} seconds")
        print(f"Start Time: {datetime.fromtimestamp(self.start_time)}")
        print(f"End Time: {datetime.fromtimestamp(self.end_time)}")
        
        print("\nTest Suite Results:")
        print("-" * 30)
        
        total_suites = len(results)
        passed_suites = sum(1 for success in results.values() if success)
        
        for suite_name, success in results.items():
            status = "PASSED" if success else "FAILED"
            print(f"  {suite_name.replace('_', ' ').title()}: {status}")
        
        print(f"\nOverall: {passed_suites}/{total_suites} test suites passed")
        
        if passed_suites == total_suites:
            print("🎉 ALL TESTS PASSED!")
        else:
            print("❌ Some tests failed. Check output above for details.")
        
        # Save report to file
        self.save_report_to_file(results, total_time)
    
    def save_report_to_file(self, results, total_time):
        """Save test report to JSON file."""
        report_data = {
            'timestamp': datetime.now().isoformat(),
            'execution_time_seconds': total_time,
            'test_results': results,
            'summary': {
                'total_suites': len(results),
                'passed_suites': sum(1 for success in results.values() if success),
                'failed_suites': sum(1 for success in results.values() if not success),
                'success_rate': sum(1 for success in results.values() if success) / len(results)
            }
        }
        
        # Create reports directory if it doesn't exist
        reports_dir = Path("test_reports")
        reports_dir.mkdir(exist_ok=True)
        
        # Save report with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = reports_dir / f"test_report_{timestamp}.json"
        
        with open(report_file, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        print(f"\nDetailed report saved to: {report_file}")


def main():
    """Main entry point for test runner."""
    parser = argparse.ArgumentParser(description="PX-UI-Client Test Runner")
    parser.add_argument("--verbose", "-v", action="store_true", 
                       help="Verbose output")
    parser.add_argument("--unit", action="store_true", 
                       help="Run only unit tests")
    parser.add_argument("--integration", action="store_true", 
                       help="Run only integration tests")
    parser.add_argument("--performance", action="store_true", 
                       help="Run only performance tests")
    parser.add_argument("--automated", action="store_true", 
                       help="Run only automated scenario tests")
    parser.add_argument("--existing", action="store_true", 
                       help="Run only existing tests")
    parser.add_argument("--skip-performance", action="store_true", 
                       help="Skip performance tests (for faster execution)")
    
    args = parser.parse_args()
    
    runner = TestRunner()
    
    # Run specific test suite if requested
    if args.unit:
        success = runner.run_unit_tests(args.verbose)
    elif args.integration:
        success = runner.run_integration_tests(args.verbose)
    elif args.performance:
        success = runner.run_performance_tests(args.verbose)
    elif args.automated:
        success = runner.run_automated_tests(args.verbose)
    elif args.existing:
        success = runner.run_existing_tests(args.verbose)
    else:
        # Run all tests
        success = runner.run_all_tests(args.verbose, args.skip_performance)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()