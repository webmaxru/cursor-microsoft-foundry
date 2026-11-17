[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
# Idempotently creates the OpenAI model deployment described in config/foundry.json.
# Read-only when a matching deployment already exists; refuses to modify a differing one.
$configPath = [IO.Path]::Combine($root, 'config', 'foundry.json')
if (-not (Test-Path $configPath)) { throw 'Copy config/foundry.example.json to config/foundry.json first.' }
$config = Get-Content $configPath -Raw | ConvertFrom-Json

function Invoke-AzureJson {
    param([string[]]$Arguments)
    $result = & az @Arguments --only-show-errors -o json
    if ($LASTEXITCODE -ne 0) { throw "Azure CLI failed: $($Arguments[0..2] -join ' ')" }
    return ($result | ConvertFrom-Json)
}

$scope = @('--subscription', $config.subscription_id, '-g', $config.resource_group, '-n', $config.account_name)
$account = Invoke-AzureJson (@('cognitiveservices', 'account', 'show') + $scope)
$projectUrl = "https://management.azure.com$($account.id)/projects/$($config.project_name)?api-version=2025-06-01"
$project = Invoke-AzureJson @('rest', '--method', 'get', '--url', $projectUrl)
if ($project.properties.endpoints.'AI Foundry API' -ne $config.project_endpoint) {
    throw 'The resolved project endpoint does not match the explicitly chosen Foundry project.'
}
$openAiEndpoint = $account.properties.endpoints.'OpenAI Language Model Instance API'
if (($openAiEndpoint.TrimEnd('/') + '/openai/v1/') -ne $config.base_url) {
    throw 'The configured inference URL does not match the Azure-discovered endpoint.'
}

$deployments = @(Invoke-AzureJson (@('cognitiveservices', 'account', 'deployment', 'list') + $scope))
$deployment = $deployments | Where-Object name -EQ $config.deployment_name
$created = $false
if ($deployment) {
    if ($deployment.properties.model.name -ne $config.model_name -or
        $deployment.properties.model.version -ne $config.model_version -or
        $deployment.sku.name -ne $config.sku_name -or
        $deployment.sku.capacity -ne $config.capacity) {
        throw 'A deployment with this name exists but differs from the configuration. Refusing to modify it.'
    }
} else {
    $models = @(Invoke-AzureJson (@('cognitiveservices', 'account', 'list-models') + $scope))
    $model = $models | Where-Object { $_.name -eq $config.model_name -and $_.version -eq $config.model_version }
    if (-not $model -or $config.sku_name -notin $model.skus.name) {
        throw 'The exact model/version/SKU is not available in this resource.'
    }
    $usage = @(Invoke-AzureJson @('cognitiveservices', 'usage', 'list', '--location', $account.location,
        '--subscription', $config.subscription_id))
    $quotaName = "OpenAI.$($config.sku_name).$($config.model_name)"
    $quota = $usage | Where-Object { $_.name.value -eq $quotaName }
    if (-not $quota -or ($quota.limit - $quota.currentValue) -lt $config.capacity) {
        throw "Insufficient or unknown quota for $quotaName. No deployment was created."
    }
    $deployment = Invoke-AzureJson (@('cognitiveservices', 'account', 'deployment', 'create') + $scope + @(
        '--deployment-name', $config.deployment_name, '--model-name', $config.model_name,
        '--model-version', $config.model_version, '--model-format', 'OpenAI',
        '--sku-name', $config.sku_name, '--sku-capacity', "$($config.capacity)"
    ))
    $created = $true
}
if ($deployment.properties.provisioningState -ne 'Succeeded') {
    throw "Deployment is not ready: $($deployment.properties.provisioningState)"
}
$evidenceDir = [IO.Path]::Combine($root, 'evidence')
New-Item $evidenceDir -ItemType Directory -Force | Out-Null
$evidence = [ordered]@{
    observed_at_utc = [DateTime]::UtcNow.ToString('o')
    created_by_this_invocation = $created
    project_id = $project.id
    project_endpoint = $config.project_endpoint
    deployment_id = $deployment.id
    deployment_name = $deployment.name
    model = $deployment.properties.model
    sku = $deployment.sku
    state = $deployment.properties.provisioningState
    rate_limits = $deployment.properties.rateLimits
    existing_deployments_before = @($deployments | Select-Object -ExpandProperty name)
}
$evidence | ConvertTo-Json -Depth 10 | Set-Content (Join-Path $evidenceDir 'deployment.json') -Encoding utf8
if ($created) {
    $evidence | ConvertTo-Json -Depth 10 | Set-Content (Join-Path $evidenceDir 'deployment-created.json') -Encoding utf8
}
$evidence | ConvertTo-Json -Depth 10
