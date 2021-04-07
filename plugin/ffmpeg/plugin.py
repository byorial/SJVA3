# -*- coding: utf-8 -*-
#########################################################
# python
import os
import traceback
import time
from datetime import datetime
from pytz import timezone

# third-party
import requests
from flask import Blueprint, request, Response, send_file, render_template, redirect, jsonify, session, send_from_directory
from flask_socketio import SocketIO, emit, send
from flask_login import login_user, logout_user, current_user, login_required
# sjva 공용
from framework import app, db, scheduler, path_app_root, socketio, path_data
from framework.logger import get_logger
from framework.util import Util

# 패키지
package_name = __name__.split('.')[0]
logger = get_logger(package_name)
from ffmpeg.logic import Logic
from ffmpeg.model import ModelSetting
from ffmpeg.interface_program_ffmpeg import Ffmpeg
from system.model import ModelSetting as SystemModelSetting


#########################################################


#########################################################
# 플러그인 공용                                       
#########################################################
blueprint = Blueprint(package_name, package_name, url_prefix='/%s' % package_name, template_folder='templates')
menu = {
    'main' : [package_name, u'FFMPEG'],
    'sub' : [
        ['setting', u'설정'], ['download', u'다운로드'], ['list', u'목록'], ['log', u'로그'],
    ]
} 

def plugin_load():
    Logic.plugin_load()    


def plugin_unload():
    Logic.plugin_unload()  

#########################################################
# WEB Menu 
#########################################################
@blueprint.route('/')
def home():
    return redirect('/%s/list' % package_name)

@blueprint.route('/<sub>')
@login_required
def detail(sub): 
    arg = ModelSetting.to_dict()
    if sub == 'setting':
        return render_template('{package_name}_{sub}.html'.format(package_name=package_name, sub=sub), arg=arg)
    elif sub == 'download':
        now = str(datetime.now(timezone('Asia/Seoul'))).replace(':', '').replace('-', '').replace(' ', '-')
        arg['temp_filename'] = ('%s' % now).split('.')[0] + '.mp4'
        return render_template('{package_name}_{sub}.html'.format(package_name=package_name, sub=sub), arg=arg)
    elif sub == 'list':
        return render_template('{package_name}_{sub}.html'.format(package_name=package_name, sub=sub), arg=arg)
    elif sub == 'log':
        return render_template('log.html', package=package_name)
    return render_template('sample.html', title='%s - %s' % (package_name, sub))

#########################################################
# For UI                                                            
#########################################################
@blueprint.route('/ajax/<sub>', methods=['GET', 'POST'])
@login_required
def ajax(sub):
    try:     
        if sub == 'setting_save':
            ret = ModelSetting.setting_save(request)
            return jsonify(ret)
        elif sub == 'ffmpeg_version':
            ret = Ffmpeg.get_version()
            return jsonify(ret)
        elif sub == 'download':
            url = request.form['url']
            filename = request.form['filename']
            ffmpeg = Ffmpeg(url, filename, call_plugin=package_name)
            data = ffmpeg.start()
            return jsonify([])
        elif sub == 'stop':
            idx = request.form['idx']
            Ffmpeg.stop_by_idx(idx)
            return jsonify([])
        elif sub == 'play':
            idx = request.form['idx']
            ffmpeg = Ffmpeg.ffmpeg_by_idx(idx)
            tmp = ffmpeg.save_fullpath.replace(path_app_root, '')
            tmp = tmp.replace('\\', '/')
            logger.debug('play : %s', tmp)
            #return redirect('/open_file%s', tmp)
            #return send_from_directory('', tmp[1:])
            return jsonify(tmp)
        elif sub == 'list':
            ret = []
            for ffmpeg in Ffmpeg.instance_list:
                ret.append(ffmpeg.get_data())
            return jsonify(ret)
    except Exception as exception: 
        logger.error('Exception:%s', exception)
        logger.error(traceback.format_exc())

#http://192.168.0.11:9999/ffmpeg/api/download?url=https%3a%2f%2fani24zo.com%2fani%2fdownload.php%3fid%3d38912&filename=test.mp4&id=0&caller=ani24&save_path=D:\
#http://192.168.0.11:9999/ffmpeg/api/status?id=0&caller=ani24
#http://192.168.0.11:9999/ffmpeg/api/stop?id=0&caller=ani24


@blueprint.route('/api/<sub>', methods=['GET', 'POST'])
def api(sub):
    sjva_token = request.args.get('token')
    if sjva_token != SystemModelSetting.get('unique'):
        ret = {}
        ret['ret'] = 'wrong_token'
        return jsonify(ret)
    if sub == 'download':
        ret = {}
        try: 
            
            max_pf_count = ModelSetting.get('max_pf_count')
            url = request.args.get('url')
            filename = request.args.get('filename')
            caller_id = request.args.get('id')
            package_name = request.args.get('caller')
            save_path = request.args.get('save_path')
            if save_path is None:
                save_path = ModelSetting.get('save_path')
            else:
                if not os.path.exists(save_path):
                    os.makedirs(save_path)    

            logger.debug('url : %s', url)
            logger.debug('filename : %s', filename)
            logger.debug('caller_id : %s', caller_id)
            logger.debug('caller : %s', package_name)
            logger.debug('save_path : %s', save_path)

            f = Ffmpeg(url, filename, plugin_id=caller_id, listener=None, max_pf_count=max_pf_count, call_plugin=package_name, save_path=save_path)
            f.start()
            ret['ret'] = 'success'
            ret['data'] = f.get_data()
        except Exception as exception: 
            logger.error('Exception:%s', exception)
            logger.error(traceback.format_exc())
            ret['ret'] = 'exception'
            ret['log'] = traceback.format_exc()    
        return jsonify(ret)
    elif sub == 'stop':
        ret = {}
        try:
            caller_id = request.args.get('id')
            package_name = request.args.get('caller')
            f = Ffmpeg.get_ffmpeg_by_caller(package_name, caller_id)
            Ffmpeg.stop_by_idx(f.idx)
            ret['ret'] = 'success'
            ret['data'] = f.get_data()
        except Exception as exception: 
            logger.error('Exception:%s', exception)
            logger.error(traceback.format_exc())
            ret['ret'] = 'exception'
            ret['log'] = traceback.format_exc()
        return jsonify(ret)
    elif sub == 'status':
        ret = {}
        try:
            caller_id = request.args.get('id')
            package_name = request.args.get('caller')
            f = Ffmpeg.get_ffmpeg_by_caller(package_name, caller_id)
            ret['ret'] = 'success'
            ret['data'] = f.get_data()
        except Exception as exception: 
            logger.error('Exception:%s', exception)
            logger.error(traceback.format_exc())
            ret['ret'] = 'exception'
            ret['log'] = traceback.format_exc()
        return jsonify(ret)




@socketio.on('connect', namespace='/%s' % package_name)
def connect():
    logger.debug('ffmpeg socketio connect')

@socketio.on('disconnect', namespace='/%s' % package_name)
def disconnect():
    logger.debug('ffmpeg socketio disconnect')
