/* ==========================================================================
   FOMOJI GROUPS + STUDENT (browser)
   Client for /api/groups/*. Same shape as connector.js: same-origin
   session cookie, no separate auth mechanism, humanized errors.
   ========================================================================== */

const FomojiGroups = (() => {
  function humanizeError(code) {
    switch (code) {
      case 'not_authenticated': return 'Sign in first.';
      case 'name_required': return 'Give the group a name.';
      case 'group_not_found': return "That group doesn't exist.";
      case 'not_a_member': return "You're not a member of that group.";
      case 'admin_required': return 'Only a group admin or owner can do that.';
      case 'owner_required': return 'Only a group owner can do that.';
      case 'last_owner': return 'A group needs at least one owner.';
      case 'identity_not_found': return "No Fomoji identity matches that ID.";
      case 'fomoji_id_required': return 'Enter a Fomoji ID to add.';
      case 'invalid_role': return 'Not a valid role.';
      case 'not_a_temporary_identity': return 'Only a temporary account can be upgraded this way.';
      default: return 'Something went wrong. Try again.';
    }
  }

  async function request(method, url, body) {
    const res = await fetch(url, {
      method,
      headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
      credentials: 'same-origin',
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.message || humanizeError(data.error));
    return data;
  }

  return {
    // ---- groups ----
    async createGroup(name, avatar, description) {
      const data = await request('POST', '/api/groups', { name, avatar, description });
      return data.group;
    },
    async listGroups() {
      const data = await request('GET', '/api/groups');
      return data.groups;
    },
    async getGroup(id) {
      return request('GET', `/api/groups/${encodeURIComponent(id)}`);
    },
    async updateGroup(id, patch) {
      const data = await request('PATCH', `/api/groups/${encodeURIComponent(id)}`, patch);
      return data.group;
    },
    async addMember(id, fomojiId, role) {
      const data = await request('POST', `/api/groups/${encodeURIComponent(id)}/members`, { fomojiId, role });
      return data.member;
    },
    async setMemberRole(id, memberId, role) {
      await request('PATCH', `/api/groups/${encodeURIComponent(id)}/members/${encodeURIComponent(memberId)}`, { role });
      return true;
    },
    async removeMember(id, memberId) {
      await request('DELETE', `/api/groups/${encodeURIComponent(id)}/members/${encodeURIComponent(memberId)}`);
      return true;
    },
    async continueAsGroup(id) {
      const data = await request('POST', `/api/groups/${encodeURIComponent(id)}/continue`);
      return data.group;
    },
    async exitGroup() {
      await request('POST', '/api/groups/exit');
      return true;
    },

    // ---- student ----
    async enrollStudent(institution) {
      const data = await request('POST', '/api/groups/student/enroll', { institution });
      return data.user;
    },
    async leaveStudent() {
      const data = await request('POST', '/api/groups/student/leave');
      return data.user;
    },
  };
})();
