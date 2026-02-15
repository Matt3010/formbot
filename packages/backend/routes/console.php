<?php

use Illuminate\Support\Facades\Schedule;
use App\Console\Commands\ScheduleTasksCommand;
use App\Console\Commands\CleanupCommand;
use App\Console\Commands\CleanupStaleEditingSessions;

Schedule::command(ScheduleTasksCommand::class)->everyMinute();
Schedule::command(CleanupCommand::class)->daily();
Schedule::command(CleanupStaleEditingSessions::class)->everyFifteenMinutes();
