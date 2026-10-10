# Relay deploy runbook

Nothing here runs without the owner's OK. Region: `us-east-1` (APNs is in the US, Budgets
and billing data live there, cheapest prices). Host latency from sa-east-1 does not matter:
one push is one call, ~150 ms.

Set once: `export AWS_REGION=us-east-1`. Use a profile that is not the live host's role.

## First deploy

1. Owner, on his Mac, with the .p8 on disk. The key goes from the file to AWS, never through a
   chat or a repo. Needs `jq`.

       jq -n --rawfile p8 /path/AuthKey_XXXXXXXXXX.p8 \
          --arg keyId XXXXXXXXXX --arg teamId YYYYYYYYYY --arg topic com.example.canarito \
          --arg master "$(openssl rand -hex 32)" \
          '{p8:$p8,keyId:$keyId,teamId:$teamId,topic:$topic,master:$master}' \
        | aws secretsmanager create-secret --name canarito/apns --secret-string file:///dev/stdin --tags Key=project,Value=canarito-relay

   (`canarito-server` must read these five fields from the secret JSON. `master` is 64 random hex chars, generated inline and never printed or saved.)

2. Stack, with the placeholder code:

       aws cloudformation deploy --stack-name canarito-relay \
         --template-file relay/deploy/template.yaml \
         --capabilities CAPABILITY_NAMED_IAM \
         --parameter-overrides MaxConcurrency=0

   `MaxConcurrency=0` means no reservation. Lambda needs 10 unreserved executions left in the
   account, so an account with the default limit of 10 cannot reserve any. Once the limit is
   raised (AWS Support case), redeploy with `MaxConcurrency=5`.

3. Real code (`handler.js` and `node_modules` if any at the zip root, built from `relay/`):

       (cd relay && zip -qr ../relay.zip . -x 'deploy/*' 'test*') 
       aws lambda update-function-code --function-name canarito-relay --zip-file fileb://relay.zip
       aws cloudformation describe-stacks --stack-name canarito-relay \
         --query 'Stacks[0].Outputs[0].OutputValue' --output text

   Delete `relay.zip` after. Do not commit it.

4. Budget by tag (optional, makes Pergamon's Lambdas not count). Tags `project=canarito-relay` are on
   every resource in the stack and on the secret. Cost allocation tags only work after:
   a) the resources exist and have billed once (the tag key appears in Billing, up to 24 h);
   b) the account owner (management account) activates `project` in Billing > Cost allocation tags,
      up to 24 h more.
   Then: `aws cloudformation deploy ... --parameter-overrides BudgetFilter=tag`.
   Until then the budget uses the service filter, which counts every Lambda, Secrets Manager
   and CloudWatch cost in the account.

5. Check: call the URL with a bad server key, expect 401/403 and a line in
   `/aws/lambda/canarito-relay`. Then one real push to the owner's phone.

## Known limits

- The per-server rate limit lives in Lambda memory, so it is per container. With the cap of 5
  concurrent containers it is bounded, not exact. Accepted. A strict limit needs a table.

## Roll back

- Code: rebuild the zip from the previous git commit and repeat step 3.
- Infra: `git checkout <old> -- relay/deploy/template.yaml` and repeat step 2.
- Stop everything now: `aws lambda put-function-concurrency --function-name canarito-relay
  --reserved-concurrent-executions 0`. Back on: same command with 5.
- Remove: `aws cloudformation delete-stack --stack-name canarito-relay` (the secret is not in the
  stack, delete it by hand with `aws secretsmanager delete-secret --secret-id canarito/apns`).

## Rotate the key

New .p8 in the Apple portal (owner), then the same jq pipe with `put-secret-value`. Keep the
current `master`: read it from the secret instead of generating a new one, or the put overwrites it.

    jq -n --rawfile p8 /path/AuthKey_NEW.p8 --arg keyId NEWKEYID --arg teamId YYYYYYYYYY \
       --arg topic com.example.canarito \
       --arg master "$(aws secretsmanager get-secret-value --secret-id canarito/apns \
           --query SecretString --output text | jq -r .master)" \
       '{p8:$p8,keyId:$keyId,teamId:$teamId,topic:$topic,master:$master}' \
     | aws secretsmanager put-secret-value --secret-id canarito/apns --secret-string file:///dev/stdin

Never rotate `master` as part of this. A new `master` invalidates every pairing and handle, so
every phone has to pair again. Only do it if `master` leaked, and tell the server operators first.

The relay caches the secret in memory (TTL max 5 min, canarito-server's code). To apply it at once:
`aws lambda update-function-configuration --function-name canarito-relay --environment
"Variables={SECRET_ID=canarito/apns,ROTATED=$(date +%s)}"`. Send a test push, then revoke the old key
in the Apple portal.

## Budget off switch

At US$5 actual spend the budget attaches `canarito-relay-off` (deny `GetSecretValue`) to the
relay role. The relay answers 5xx, servers see it as down. Billing data lags up to ~12 h, so the
concurrency cap is the real brake and the budget the backstop. To turn on again: detach the policy

    aws iam detach-role-policy --role-name canarito-relay \
      --policy-arn arn:aws:iam::<account>:policy/canarito-relay-off
