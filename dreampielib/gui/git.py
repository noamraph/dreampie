# Copyright 2012 Noam Yorav-Raphael
#
# This file is part of DreamPie.
# 
# DreamPie is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# DreamPie is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with DreamPie.  If not, see <http://www.gnu.org/licenses/>.

all = ['get_commit_details']

from os.path import abspath, join, dirname, isdir

def get_commit_details():
    """
    If there's a '.git' directory besides 'dreampielib', return the current
    commit (HEAD) id and commit time.
    Otherwise, return None, None.
    """
    git_dir = join(dirname(dirname(dirname(abspath(__file__)))), '.git')
    if not isdir(git_dir):
        return None, None
    try:
        from dulwich.repo import Repo
    except ImportError:
        return None, None
    
    repo = Repo(git_dir)
    commit_id = repo.refs['HEAD']
    commit = repo.commit(commit_id)
    return commit_id, commit.commit_time
