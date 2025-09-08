#!/usr/bin/env python3
"""
Script to minimize seccomp.json for a Flask application container.

This script systematically removes system calls from the seccomp profile
while ensuring the container can still:
1. Start without errors
2. Respond within a timeout
3. Serve HTTP requests
4. Handle form submissions and file writing
"""

import json
import subprocess
import time
import requests
import sys
import os
from typing import List, Dict, Any

# Verbose flag for detailed output
VERBOSE = True

def log(message: str):
    """Print verbose messages if enabled."""
    if VERBOSE:
        print(f"[INFO] {message}")

def stop_all_containers():
    """Stop and remove all running Docker containers."""
    log("Stopping all running Docker containers...")
    try:
        # Get list of running containers
        result = subprocess.run(
            ["docker", "ps", "-q"], 
            capture_output=True, 
            text=True
        )
        
        if result.stdout.strip():
            container_ids = result.stdout.strip().split('\n')
            log(f"Found {len(container_ids)} running containers")
            
            # Stop all containers
            subprocess.run(
                ["docker", "stop"] + container_ids,
                check=True,
                capture_output=True
            )
            log("All containers stopped successfully")
            
            # Remove all containers
            subprocess.run(
                ["docker", "rm"] + container_ids,
                check=True,
                capture_output=True
            )
            log("All containers removed successfully")
        else:
            log("No running containers found")
    except subprocess.CalledProcessError as e:
        log(f"Warning: Failed to stop/remove containers: {e}")

def load_seccomp_profile(filepath: str) -> Dict[str, Any]:
    """Load seccomp profile from JSON file."""
    log(f"Loading seccomp profile from {filepath}")
    with open(filepath, 'r') as f:
        return json.load(f)

def save_seccomp_profile(profile: Dict[str, Any], filepath: str):
    """Save seccomp profile to JSON file."""
    log(f"Saving seccomp profile to {filepath}")
    with open(filepath, 'w') as f:
        json.dump(profile, f, indent=2)

def get_all_syscalls(profile: Dict[str, Any]) -> List[str]:
    """Extract all system call names from the seccomp profile."""
    syscalls = []
    for syscall_group in profile.get('syscalls', []):
        syscalls.extend(syscall_group.get('names', []))
    return sorted(list(set(syscalls)))

def remove_syscall_from_profile(profile: Dict[str, Any], syscall_name: str) -> Dict[str, Any]:
    """Create a new profile with the specified syscall removed."""
    new_profile = json.loads(json.dumps(profile))  # Deep copy
    
    # Remove syscall from all syscall groups
    for syscall_group in new_profile.get('syscalls', []):
        if 'names' in syscall_group and syscall_name in syscall_group['names']:
            syscall_group['names'].remove(syscall_name)
            # If the group is now empty, we might want to remove it
            # But we'll keep it for now to maintain structure
    
    return new_profile

def run_container_with_profile(profile_path: str, timeout: int = 30) -> bool:
    """
    Run the container with the given seccomp profile.
    Returns True if successful, False otherwise.
    """
    log(f"Testing container with profile: {profile_path}")
    
    try:
        # Run container in background
        cmd = [
            "docker", "run", "-d", "--rm",
            f"--security-opt=seccomp={profile_path}",
            "--security-opt=apparmor=apparmor-flask",
            "-p", "5000:5000",
            "flask:0.0.3"
        ]
        
        log(f"Executing: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        if result.returncode != 0:
            log(f"Container failed to start: {result.stderr}")
            return False
            
        container_id = result.stdout.strip()
        log(f"Container started with ID: {container_id}")
        
        # Wait a bit for the container to initialize
        time.sleep(5)
        
        # Check if container is still running
        inspect_result = subprocess.run(
            ["docker", "inspect", container_id],
            capture_output=True,
            text=True
        )
        
        if inspect_result.returncode != 0:
            log("Failed to inspect container")
            return False
            
        container_info = json.loads(inspect_result.stdout)
        if not container_info[0]['State']['Running']:
            log("Container is not running")
            # Get logs to see what went wrong
            logs_result = subprocess.run(
                ["docker", "logs", container_id],
                capture_output=True,
                text=True
            )
            if logs_result.returncode == 0:
                log(f"Container logs: {logs_result.stdout}")
            return False
            
        log("Container is running")
        return True
        
    except subprocess.TimeoutExpired:
        log("Container start timed out")
        return False
    except Exception as e:
        log(f"Error running container: {e}")
        return False

def test_web_functionality() -> bool:
    """
    Test if the web application is functioning correctly.
    Returns True if all tests pass, False otherwise.
    """
    log("Testing web functionality...")
    
    try:
        # Test 1: Check if the main page loads
        log("Testing main page access...")
        response = requests.get("http://localhost:5000/", timeout=10)
        if response.status_code != 200:
            log(f"Main page failed with status {response.status_code}")
            return False
        log("Main page loaded successfully")
        
        # Test 2: Test form submission
        log("Testing form submission...")
        response = requests.post(
            "http://localhost:5000/write",
            data={"content": "test_content"},
            timeout=10
        )
        if response.status_code != 200:
            log(f"Form submission failed with status {response.status_code}")
            return False
        log("Form submission successful")
        
        # Test 3: Test API endpoint
        log("Testing API endpoint...")
        response = requests.post(
            "http://localhost:5000/api/write",
            json={"text": "api_test_content"},
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        if response.status_code != 200:
            log(f"API endpoint failed with status {response.status_code}")
            return False
        log("API endpoint successful")
        
        return True
        
    except requests.exceptions.RequestException as e:
        log(f"Web functionality test failed: {e}")
        return False
    except Exception as e:
        log(f"Unexpected error during web testing: {e}")
        return False

def stop_container():
    """Stop the test container."""
    try:
        # Find and stop the container
        result = subprocess.run(
            ["docker", "ps", "-q", "--filter", "ancestor=flask:0.0.3"],
            capture_output=True,
            text=True
        )
        
        if result.stdout.strip():
            container_ids = result.stdout.strip().split('\n')
            for container_id in container_ids:
                subprocess.run(
                    ["docker", "stop", container_id],
                    capture_output=True
                )
                log(f"Stopped container {container_id}")
    except Exception as e:
        log(f"Error stopping container: {e}")

def minimize_seccomp_profile():
    """Main function to minimize the seccomp profile."""
    log("Starting seccomp profile minimization...")
    
    # Stop all containers first
    stop_all_containers()
    
    # Load the default profile (permissive)
    default_profile = load_seccomp_profile("seccomp-default.json")
    
    # Create initial working profile (copy of default)
    working_profile = json.loads(json.dumps(default_profile))
    working_profile_path = "seccomp.json"
    save_seccomp_profile(working_profile, working_profile_path)
    
    # Get all syscalls
    all_syscalls = get_all_syscalls(working_profile)
    log(f"Found {len(all_syscalls)} system calls to test")
    
    # List of syscalls we've determined are necessary
    necessary_syscalls = set()
    
    # Test each syscall
    for i, syscall in enumerate(all_syscalls):
        log(f"Testing syscall {i+1}/{len(all_syscalls)}: {syscall}")
        
        # Create a profile without this syscall
        test_profile = remove_syscall_from_profile(working_profile, syscall)
        test_profile_path = f"seccomp_test_{syscall}.json"
        save_seccomp_profile(test_profile, test_profile_path)
        
        try:
            # Stop any existing container
            stop_container()
            
            # Test the profile
            if run_container_with_profile(test_profile_path):
                # If container starts, test web functionality
                if test_web_functionality():
                    log(f"Syscall {syscall} is NOT necessary - can be removed")
                    # Update working profile to remove this syscall
                    working_profile = test_profile
                    save_seccomp_profile(working_profile, working_profile_path)
                else:
                    log(f"Syscall {syscall} is necessary for web functionality")
                    necessary_syscalls.add(syscall)
            else:
                log(f"Syscall {syscall} is necessary for container startup")
                necessary_syscalls.add(syscall)
                
        except Exception as e:
            log(f"Error testing syscall {syscall}: {e}")
            necessary_syscalls.add(syscall)
        finally:
            # Stop container and clean up test profile
            stop_container()
            try:
                os.remove(test_profile_path)
            except:
                pass
    
    # Final cleanup
    stop_container()
    
    # Save the minimized profile
    save_seccomp_profile(working_profile, "seccomp-minimized.json")
    
    # Report results
    log("=== MINIMIZATION COMPLETE ===")
    log(f"Necessary syscalls ({len(necessary_syscalls)}):")
    for syscall in sorted(necessary_syscalls):
        log(f"  - {syscall}")
    
    log(f"Minimized profile saved as seccomp-minimized.json")
    log("You can now use this profile with your container")

if __name__ == "__main__":
    try:
        minimize_seccomp_profile()
    except KeyboardInterrupt:
        log("Minimization interrupted by user")
        stop_container()
        sys.exit(1)
    except Exception as e:
        log(f"Minimization failed with error: {e}")
        stop_container()
        sys.exit(1)
