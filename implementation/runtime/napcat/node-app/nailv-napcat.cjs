// Dedicated QQ data path; no ordinary QQ profile or old-bot login data is loaded.
const path = require('path');
const fs = require('fs');
const {pathToFileURL} = require('url');
const root = __dirname;
const profile = path.join(root,'qq-profile');
fs.mkdirSync(profile,{recursive:true});
const wrapperPath = path.join(root,'wrapper.node');
process.env.NAPCAT_WRAPPER_PATH = wrapperPath;
process.env.NAPCAT_QQ_PACKAGE_INFO_PATH = path.join(root,'package.json');
process.env.NAPCAT_QQ_VERSION_CONFIG_PATH = path.join(root,'config.json');
process.env.NAPCAT_DISABLE_PIPE = '1';
process.env.NAPCAT_DISABLE_TIME_SYNC = '1';
// The isolated package's two path-resolution sites honor this explicit root.
// Native addon getters are read-only, so the separate bootstrap does not mutate them.
process.env.NAILV_QQ_DATA_ROOT = profile;
import(pathToFileURL(path.join(root,'napcat','napcat.mjs')).href);
