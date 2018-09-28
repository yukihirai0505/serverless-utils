## Setup

```
$ cp config.sample.json config.json
```

Edit `config.json`

```
{
  "SLACK_CHANNEL": "#<YOUR CHANNEL NAME>",
  "HOOK_URL": "hooks.slack.com/services/{YOUR HOOK}"
}
```

## Local Test

```
$ npx sls invoke local -f hello --path test/code_deploy_created.json
```

## Deploy


```
$ npx sls deploy --aws-profile <!YOUR AWS PROFILE NAME>
```

ref: https://serverless.com/framework/docs/providers/aws/guide/credentials/

If you use codedeploy, set a trigger for SNS => `slack-notify`
