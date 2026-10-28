# GitHub发布与后续维护

采用独立干净仓库，只提交源码、模板、虚构示例与文档。不要把原项目根目录或内部最终交付ZIP直接推到GitHub。

## 本地发布检查

```bash
python scripts/check_release.py
python -m unittest discover -s tests -v
python scripts/offline_demo.py
git status --short
git diff --cached --stat
```

检查实际已跟踪文件，而不是只看.gitignore。密钥一旦进入提交历史，仅新增ignore并不能撤回。若发生泄露，先撤销/轮换密钥，再按GitHub官方流程处理历史。

## 建仓库与首发

本地Git和官方gh登录后，可用以下标准流程。新仓库别名以实际账户为准；存在同名仓库时先检查，不覆盖他人的内容。

```bash
git init -b main
git add .
git commit -m "Initial public source release"
gh repo create nailv-voice-bot --public --source . --remote origin --push
git tag -a v0.1.0 -m "v0.1.0 source preview"
git push origin v0.1.0
gh release create v0.1.0 --title "v0.1.0 · Source preview" --notes-file docs/releases/v0.1.0.md --prerelease
```

gh登录/授权由账号所有者在GitHub官方页面完成，密码和Token不应发到Issue或对话。CI无需模型和密钥，默认不调用收费接口。

## 版本策略

main保持可离线检查；功能改动走分支/PR。先更新CHANGELOG、配置迁移和验证记录，再打版本tag。v0.1.0标为prerelease，因为公开配置副本未重新完成GPU/QQ验收。改进后可以根据实际验证发布稳定版。

GitHub自动Source code ZIP只包括跟踪源码。不要把私有模型/数据附到Release。将来要发布权重，应逐项核对模型许可、素材与声音授权，另建模型说明与来源/训练卡；软件AGPL不覆盖这些权利。

参考：[GitHub仓库实践](https://docs.github.com/en/repositories/creating-and-managing-repositories/best-practices-for-repositories)、[发布版本](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)、[敏感数据处理](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)。
