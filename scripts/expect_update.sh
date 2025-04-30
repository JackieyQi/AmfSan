#!/usr/bin/env expect

# Set timeout for commands (in seconds)
set timeout 30

# Store the sudo password
set password "123456"

# Start the script execution
spawn bash -c {
    cd /home/yyq/AmfSan && git pull &&
    cd /home/yyq/AmfSan_script && git pull &&
    sudo supervisorctl restart all &&
    sudo supervisorctl status
}

# Handle sudo password prompts
expect {
    "password for" {
        send "$password\r"
        exp_continue
    }
    "sudo" {
        exp_continue
    }
}

# Wait for the process to finish
catch wait result

# Exit with the same status as the spawned process
exit [lindex $result 3]