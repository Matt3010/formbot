<?php

use Illuminate\Support\Facades\Schedule;
use App\Console\Commands\ScheduleTasksCommand;
use App\Console\Commands\CleanupCommand;

Schedule::command(ScheduleTasksCommand::class)->everyMinute();
Schedule::command(CleanupCommand::class)->daily();
