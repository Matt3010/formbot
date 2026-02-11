<?php

return [

    'retention_days' => env('FORMBOT_RETENTION_DAYS', 30),

    'default_action_delay_ms' => env('FORMBOT_DEFAULT_DELAY', 500),

    'max_parallel_global' => env('FORMBOT_MAX_PARALLEL', 5),

    'default_ollama_model' => env('OLLAMA_MODEL', 'llama3.1:8b'),

];
